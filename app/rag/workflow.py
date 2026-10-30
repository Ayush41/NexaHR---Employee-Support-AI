import logging
import json
import urllib.request
import urllib.error
from typing import Literal
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, START, END
from app.core.config import get_settings
from app.rag.state import AgentState, RouteDecision, EvidenceGrade
from app.rag.vectorstore import get_retriever

logger = logging.getLogger(__name__)
settings = get_settings()

_llm = None
_web_search = None
_cached_groq_model: tuple[str, str, str] | None = None


def get_active_groq_model(clean_key: str, requested_model: str) -> str:
    global _cached_groq_model
    if _cached_groq_model and _cached_groq_model[:2] == (clean_key, requested_model):
        return _cached_groq_model[2]

    try:
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {clean_key}"}
        )
        req.add_header("Authorization", "Bearer " + clean_key)
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            available_models = [m["id"] for m in data.get("data", [])]

            if requested_model not in available_models:
                raise RuntimeError(
                    f"Configured Groq model '{requested_model}' is not available for this API key. "
                    "Set GROQ_MODEL to an available model ID; /api/groq-models lists the IDs "
                    "available to this key."
                )

    except RuntimeError:
        raise
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode()
        logger.error(f"Groq API error when querying models: {e.code} - {err_msg}")
        if e.code == 401:
            raise RuntimeError(f"Invalid GROQ_API_KEY. Groq returned 401 Unauthorized: {err_msg}")
    except Exception as e:
        logger.warning(f"Could not reach Groq models endpoint: {e}")

    model_to_use = requested_model or "openai/gpt-oss-120b"
    _cached_groq_model = (clean_key, requested_model, model_to_use)
    return model_to_use


def llm():
    global _llm
    if _llm is None:
        clean_key = settings.groq_api_key.strip().strip('"').strip("'")
        clean_model = settings.groq_model.strip().strip('"').strip("'")

        if clean_key:
            model_to_use = get_active_groq_model(clean_key, clean_model)
            logger.info(f"Initializing ChatGroq with model: {model_to_use}")
            _llm = ChatGroq(
                model=model_to_use,
                temperature=0,
                api_key=clean_key,
            )
        elif settings.openai_api_key:
            from langchain_openai import ChatOpenAI
            _llm = ChatOpenAI(
                model=settings.openai_model,
                temperature=0,
                api_key=settings.openai_api_key.strip().strip('"').strip("'"),
            )
        else:
            raise RuntimeError("GROQ_API_KEY is missing. Please set GROQ_API_KEY in your .env file.")
    return _llm


def web_search_tool():
    global _web_search
    if _web_search is None:
        clean_tavily = settings.tavily_api_key.strip().strip('"').strip("'")
        if not clean_tavily:
            raise RuntimeError("TAVILY_API_KEY is missing")
        _web_search = TavilySearch(
            tavily_api_key=clean_tavily,
            max_results=5,
            topic="general",
            include_answer=True,
            include_raw_content=False,
        )
    return _web_search


def add_trace(state: AgentState, message: str):
    return [*state.get("trace", []), message]


def route_question(state: AgentState):
    router = llm().with_structured_output(
        RouteDecision,
        method="json_schema",
        strict=True,
    )
    decision = router.invoke(f"""
You route messages for an enterprise HR policy and employee support assistant.
Use kb for questions about company HR policies, leave, holidays, benefits, payroll,
remote work, attendance, onboarding, performance, expenses, travel, conduct, or employee support.
Use direct only for greetings, thanks, or casual chat that needs no company knowledge.
Question: {state['question']}
Return valid JSON like {{"route":"kb"}}.
""")
    route = getattr(decision, "route", None)
    if route is None and isinstance(decision, dict):
        route = decision.get("route", "kb")
    route = route or "kb"
    return {"source_used": route, "trace": add_trace(state, f"Router → {route.upper()}")}


def route_after_router(state: AgentState) -> Literal["retrieve_kb", "direct_answer"]:
    return "retrieve_kb" if state["source_used"] == "kb" else "direct_answer"


def retrieve_kb(state: AgentState):
    docs = get_retriever().invoke(state["current_query"])
    return {"kb_docs": docs, "trace": add_trace(state, f"Private KB retrieval → {len(docs)} chunks")}


def grade_kb(state: AgentState):
    grader = llm().with_structured_output(
        EvidenceGrade,
        method="json_schema",
        strict=True,
    )
    context = "\n\n".join(f"Source: {d.metadata.get('source','unknown')}\n{d.page_content}" for d in state["kb_docs"])
    grade_obj = grader.invoke(f"""
You grade evidence for an enterprise HR policy and employee support assistant.
Question: {state['question']}
Private company HR KB evidence:\n{context}
Return good only if the evidence is sufficient to answer confidently and specifically.
Otherwise return weak. JSON: {{"grade":"good"}} or {{"grade":"weak"}}.
""")
    grade = getattr(grade_obj, "grade", None)
    if grade is None and isinstance(grade_obj, dict):
        grade = grade_obj.get("grade", "weak")
    grade = grade or "weak"
    return {"kb_grade": grade, "trace": add_trace(state, f"KB evidence grade → {grade.upper()}")}


def after_kb(state: AgentState) -> Literal["generate_from_kb", "search_web"]:
    return "generate_from_kb" if state["kb_grade"] == "good" else "search_web"


def search_web(state: AgentState):
    result = web_search_tool().invoke({"query": state["current_query"]})
    lines, citations = [], []
    if isinstance(result, dict):
        if result.get("answer"):
            lines.append("Search answer: " + result["answer"])
        for item in result.get("results", []):
            title, url, content = item.get("title", ""), item.get("url", ""), item.get("content", "")
            lines.append(f"Title: {title}\nURL: {url}\nContent: {content}")
            citations.append({"title": title or url, "url": url, "type": "web"})
    else:
        lines.append(str(result))
    return {
        "web_results": "\n\n".join(lines),
        "citations": citations,
        "source_used": "web",
        "trace": add_trace(state, "Web fallback → Tavily search"),
    }


def grade_web(state: AgentState):
    grader = llm().with_structured_output(
        EvidenceGrade,
        method="json_schema",
        strict=True,
    )
    grade_obj = grader.invoke(f"""
Question: {state['question']}
Web evidence:\n{state['web_results']}
Return good if the evidence is sufficient and directly relevant; otherwise weak.
Return valid JSON like {{"grade":"good"}}.
""")
    grade = getattr(grade_obj, "grade", None)
    if grade is None and isinstance(grade_obj, dict):
        grade = grade_obj.get("grade", "weak")
    grade = grade or "weak"
    return {"web_grade": grade, "trace": add_trace(state, f"Web evidence grade → {grade.upper()}")}


def after_web(state: AgentState) -> Literal["generate_from_web", "rewrite_query", "insufficient"]:
    if state["web_grade"] == "good":
        return "generate_from_web"
    if state["retry_count"] < settings.max_retries:
        return "rewrite_query"
    return "insufficient"


def rewrite_query(state: AgentState):
    res = llm().invoke(f"""
Rewrite this HR/employee-support question for better private knowledge retrieval and public web search.
Preserve intent, add useful HR/policy keywords, do not answer, return only the query.
Question: {state['question']}
""")
    rewritten = res.content.strip() if hasattr(res, "content") else str(res).strip()
    return {
        "current_query": rewritten,
        "retry_count": state["retry_count"] + 1,
        "trace": add_trace(state, f"Query rewrite → {rewritten}"),
    }


def generate_from_kb(state: AgentState):
    context = "\n\n".join(f"[Source: {d.metadata.get('source','unknown')}]\n{d.page_content}" for d in state["kb_docs"])
    res = llm().invoke(f"""
You are an enterprise HR policy and employee support copilot for NexaHR. Answer ONLY from the private company HR KB below.
Be concise, practical, respectful, and policy-grounded. If steps are present, present them clearly.
Do not invent policy details. Mention that the answer is based on the company's private knowledge base.
Question: {state['question']}\n\nPrivate KB:\n{context}
""")
    answer = res.content if hasattr(res, "content") else str(res)
    citations = []
    seen = set()
    for d in state["kb_docs"]:
        src = d.metadata.get("source", "Private KB")
        if src not in seen:
            seen.add(src)
            citations.append({"title": src.replace("\\", "/").split("/")[-1], "url": "", "type": "private_kb"})
    return {"answer": answer, "source_used": "private_kb", "citations": citations, "trace": add_trace(state, "Answer generation → PRIVATE KB")}


def generate_from_web(state: AgentState):
    res = llm().invoke(f"""
You are an enterprise HR policy and employee support copilot for NexaHR. The private company HR KB was insufficient.
Answer ONLY from the web evidence below. Clearly say this is external public information and may require HR validation before being treated as company policy or employment guidance.
Question: {state['question']}\n\nWeb evidence:\n{state['web_results']}
""")
    answer = res.content if hasattr(res, "content") else str(res)
    return {"answer": answer, "source_used": "web_search", "trace": add_trace(state, "Answer generation → WEB SEARCH")}


def direct_answer(state: AgentState):
    res = llm().invoke(f"You are NexaHR, an HR copilot. Respond briefly, professionally, and naturally to: {state['question']}")
    answer = res.content if hasattr(res, "content") else str(res)
    return {"answer": answer, "source_used": "direct", "trace": add_trace(state, "Direct response → no retrieval")}


def insufficient(state: AgentState):
    return {
        "answer": "I couldn't find enough reliable evidence in the company HR knowledge base or external search to answer confidently. Please contact the HR team or provide more details.",
        "source_used": "insufficient_evidence",
        "trace": add_trace(state, "Stopped → insufficient reliable evidence"),
    }


def build_graph():
    graph = StateGraph(AgentState)
    for name, fn in {
        "route_question": route_question,
        "retrieve_kb": retrieve_kb,
        "grade_kb": grade_kb,
        "search_web": search_web,
        "grade_web": grade_web,
        "rewrite_query": rewrite_query,
        "generate_from_kb": generate_from_kb,
        "generate_from_web": generate_from_web,
        "direct_answer": direct_answer,
        "insufficient": insufficient,
    }.items():
        graph.add_node(name, fn)
    graph.add_edge(START, "route_question")
    graph.add_conditional_edges("route_question", route_after_router, {
        "retrieve_kb": "retrieve_kb", "direct_answer": "direct_answer"
    })
    graph.add_edge("retrieve_kb", "grade_kb")
    graph.add_conditional_edges("grade_kb", after_kb, {
        "generate_from_kb": "generate_from_kb", "search_web": "search_web"
    })
    graph.add_edge("search_web", "grade_web")
    graph.add_conditional_edges("grade_web", after_web, {
        "generate_from_web": "generate_from_web", "rewrite_query": "rewrite_query", "insufficient": "insufficient"
    })
    graph.add_edge("rewrite_query", "retrieve_kb")
    graph.add_edge("generate_from_kb", END)
    graph.add_edge("generate_from_web", END)
    graph.add_edge("direct_answer", END)
    graph.add_edge("insufficient", END)
    return graph.compile()


agent_graph = build_graph()


def initial_state(question: str) -> AgentState:
    return {
        "question": question,
        "current_query": question,
        "kb_docs": [],
        "web_results": "",
        "kb_grade": "",
        "web_grade": "",
        "answer": "",
        "source_used": "",
        "retry_count": 0,
        "trace": [],
        "citations": [],
    }


def ask(question: str):
    initial = initial_state(question)
    return agent_graph.invoke(initial)


def stream_ask(question: str):
    state = initial_state(question)
    for update in agent_graph.stream(state, stream_mode="updates"):
        for node, values in update.items():
            state.update(values)
            safe_values = {
                key: value
                for key, value in values.items()
                if key in {
                    "source_used",
                    "kb_grade",
                    "web_grade",
                    "trace",
                    "answer",
                    "citations",
                }
            }
            if node == "retrieve_kb":
                safe_values["retrieved_chunks"] = len(values.get("kb_docs", []))
            yield {"type": "step", "node": node, "data": safe_values}

    yield {
        "type": "complete",
        "result": {
            key: state[key]
            for key in (
                "answer",
                "source_used",
                "trace",
                "citations",
                "current_query",
            )
        },
    }
