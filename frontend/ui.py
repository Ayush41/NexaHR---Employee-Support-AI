import html

import requests
import streamlit as st

from frontend import config

WORKFLOW_STEPS = [
    ("route_question", "Route question"),
    ("retrieve_kb", "Retrieve private KB"),
    ("grade_kb", "Grade evidence"),
    ("search_web", "Tavily fallback if weak"),
    ("rewrite_query", "Rewrite and retry if needed"),
    ("generate", "Grounded answer"),
]

NODE_TO_STEP = {
    "route_question": "route_question",
    "retrieve_kb": "retrieve_kb",
    "grade_kb": "grade_kb",
    "search_web": "search_web",
    "grade_web": "search_web",
    "rewrite_query": "rewrite_query",
    "generate_from_kb": "generate",
    "generate_from_web": "generate",
    "direct_answer": "generate",
    "insufficient": "generate",
    "employee_leave_balance": "generate",
}


def load_styles() -> None:
    css = (config.ROOT_DIR / "frontend" / "styles.css").read_text(
        encoding="utf-8"
    )
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_brand() -> None:
    st.markdown(
        """
        <div class="brand-lockup">
            <span class="brand-mark">N</span>
            <div>
                <div class="brand-name">NexaHR</div>
                <div class="brand-subtitle">Employee Support</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_workflow_panel(container, events: list[dict], running: bool) -> None:
    seen_nodes = {event.get("node") for event in events}
    route = next(
        (
            event.get("data", {}).get("source_used")
            for event in events
            if event.get("node") == "route_question"
        ),
        None,
    )
    kb_grade = next(
        (
            event.get("data", {}).get("kb_grade")
            for event in events
            if event.get("node") == "grade_kb"
        ),
        None,
    )
    web_grade = next(
        (
            event.get("data", {}).get("web_grade")
            for event in events
            if event.get("node") == "grade_web"
        ),
        None,
    )
    steps = []
    for index, (step_id, label) in enumerate(WORKFLOW_STEPS):
        visited = any(NODE_TO_STEP.get(node) == step_id for node in seen_nodes if node)
        if visited:
            state = "done"
        else:
            skipped = (
                (route == "direct" and step_id in {"retrieve_kb", "grade_kb", "search_web", "rewrite_query"})
                or (
                    route == "employee_leave_records"
                    and step_id in {"retrieve_kb", "grade_kb", "search_web", "rewrite_query"}
                )
                or (step_id == "search_web" and kb_grade == "good")
                or (step_id == "rewrite_query" and web_grade == "good")
                or (step_id == "rewrite_query" and "insufficient" in seen_nodes)
                or (
                    step_id == "rewrite_query"
                    and (
                        "generate_from_kb" in seen_nodes
                        or "direct_answer" in seen_nodes
                    )
                )
            )
            if skipped:
                continue
            earlier_steps = [key for key, _ in WORKFLOW_STEPS[:index]]
            earlier_steps_done = all(
                any(NODE_TO_STEP.get(node) == key for node in seen_nodes if node)
                or (
                    key == "search_web"
                    and kb_grade == "good"
                )
                or (
                    key == "rewrite_query"
                    and (web_grade == "good" or "insufficient" in seen_nodes)
                )
                or (
                    route == "direct"
                    and key in {"retrieve_kb", "grade_kb", "search_web", "rewrite_query"}
                )
                or (
                    route == "employee_leave_records"
                    and key in {"retrieve_kb", "grade_kb", "search_web", "rewrite_query"}
                )
                for key in earlier_steps
            )
            state = "active" if running and earlier_steps_done else "pending"
        if state == "skipped":
            continue
        badge = "✓" if state == "done" else "•" if state == "active" else step_id[0].upper()
        steps.append(
            f'<div class="workflow-step {state}">'
            f'<span class="step-badge">{badge}</span>'
            f'<span>{html.escape(label)}</span></div>'
        )

    with container.container():
        st.markdown(
            '<div class="workflow-card">'
            '<div class="panel-heading">LangGraph workflow</div>'
            '<div class="panel-caption">How NexaHR finds a grounded answer</div>'
            + "".join(steps)
            + "</div>",
            unsafe_allow_html=True,
        )
        trace = [
            line
            for event in events
            for line in event.get("data", {}).get("trace", [])
        ]
        trace = list(dict.fromkeys(trace))
        st.markdown(
            '<div class="trace-card">'
            '<div class="panel-heading">Agent trace</div>'
            '<div class="panel-caption">LangGraph decisions as the request runs</div>'
            + (
                "".join(
                    '<div class="trace-line"><span class="trace-dot">●</span>'
                    f"{html.escape(line)}</div>"
                    for line in trace
                )
                if trace
                else '<div class="source-empty">Trace will appear when you ask a question.</div>'
            )
            + "</div>",
            unsafe_allow_html=True,
        )

        source = st.session_state.get("last_source", "")
        source_labels = {
            "private_kb": "Private knowledge base",
            "web_search": "Tavily web search",
            "web": "Tavily web search",
            "direct": "Direct response",
            "insufficient_evidence": "Insufficient evidence",
            "employee_leave_records": "Employee leave records (demo)",
        }
        source_content = (
            f'<div class="source-value">{html.escape(source_labels.get(source, source))}</div>'
            if source
            else '<div class="source-empty">The final answer source will appear here.</div>'
        )
        st.markdown(
            '<div class="source-card">'
            '<div class="panel-heading">Final source</div>'
            + source_content
            + "</div>",
            unsafe_allow_html=True,
        )


def render_sidebar() -> None:
    with st.sidebar:
        render_brand()
        role = st.session_state.get("role", "Employee")
        st.caption("HR & management workspace" if role == "Admin" else "Employee workspace")
        if st.button("Sign out", use_container_width=True):
            st.session_state.clear()
            st.rerun()

        if role == "Admin":
            st.divider()
            st.markdown("#### Policy knowledge")
            st.caption("Add an approved document to the private HR knowledge base.")
            uploaded_file = st.file_uploader(
                "Policy document",
                type=["pdf", "docx", "txt", "md"],
                label_visibility="collapsed",
            )
            if st.button(
                "Upload and index",
                type="primary",
                disabled=uploaded_file is None,
                use_container_width=True,
            ):
                from frontend.api import upload_document

                try:
                    with st.spinner("Indexing policy document..."):
                        result = upload_document(uploaded_file)
                    st.success(
                        f"Indexed {result['file']} ({result['chunks']} chunks)."
                    )
                except (
                    requests.RequestException,
                    RuntimeError,
                    ValueError,
                    KeyError,
                ) as exc:
                    st.error(str(exc))
        else:
            st.divider()
            st.markdown("#### Your HR assistant")
            st.caption("Ask questions about company policies and workplace support.")

        st.divider()
        st.caption(f"Connected API · {config.API_BASE_URL}")


def render_chat_history() -> None:
    for message in st.session_state.get("messages", []):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            citations = message.get("citations", [])
            if citations:
                with st.expander("Sources"):
                    for citation in citations:
                        title = html.escape(citation.get("title", "Reference"))
                        url = citation.get("url")
                        if url and url.startswith(("https://", "http://")):
                            st.markdown(f"- [{title}]({url})")
                        else:
                            st.markdown(f"- {title}")
