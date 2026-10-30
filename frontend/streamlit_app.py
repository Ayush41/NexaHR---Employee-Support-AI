from typing import Any

import requests
import streamlit as st

from frontend.api import check_health, stream_chat
from frontend.auth import render_login
from frontend.ui import (
    load_styles,
    render_chat_history,
    render_sidebar,
    render_workflow_panel,
)

st.set_page_config(
    page_title="NexaHR Employee Support",
    page_icon="N",
    layout="wide",
    initial_sidebar_state="expanded",
)
load_styles()


def consume_chat(question: str, workflow_panel: Any) -> None:
    events: list[dict] = []
    result: dict = {}
    st.session_state["last_source"] = ""
    st.session_state["last_trace"] = []

    with st.chat_message("assistant"):
        answer_placeholder = st.empty()
        answer_placeholder.markdown(
            '<span class="panel-caption">Following the LangGraph workflow…</span>',
            unsafe_allow_html=True,
        )
        try:
            for event in stream_chat(question):
                if event.get("type") == "step":
                    events.append(event)
                    st.session_state["last_events"] = events.copy()
                    st.session_state["last_trace"] = [
                        line
                        for item in events
                        for line in item.get("data", {}).get("trace", [])
                    ]
                    render_workflow_panel(workflow_panel, events, running=True)
                elif event.get("type") == "complete":
                    result = event.get("result", {})
                elif event.get("type") == "error":
                    raise RuntimeError(event.get("message", "The chat request failed."))

            if not result:
                raise RuntimeError("The chat stream ended before returning an answer.")

            answer = result.get("answer", "The API returned no answer.")
            citations = result.get("citations", [])
            trace = result.get("trace", [])
            source = result.get("source_used", "")
            st.session_state["last_trace"] = trace
            st.session_state["last_events"] = events.copy()
            st.session_state["last_source"] = source

            answer_placeholder.markdown(answer)
            if citations:
                with st.expander("Sources"):
                    for citation in citations:
                        title = citation.get("title", "Reference")
                        url = citation.get("url")
                        if url and url.startswith(("https://", "http://")):
                            st.markdown(f"- [{title}]({url})")
                        else:
                            st.markdown(f"- {title}")

            st.session_state.setdefault("messages", []).append(
                {
                    "role": "assistant",
                    "content": answer,
                    "citations": citations,
                }
            )
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            answer = str(exc)
            answer_placeholder.error(answer)
            st.session_state.setdefault("messages", []).append(
                {"role": "assistant", "content": answer}
            )
    if events:
        render_workflow_panel(workflow_panel, events, running=False)


if not st.session_state.get("authenticated", False):
    st.markdown('<div class="page-kicker">NEXAHR · EMPLOYEE SUPPORT</div>', unsafe_allow_html=True)
    left, right = st.columns([1.05, 0.95], gap="large", vertical_alignment="center")
    with left:
        render_login()
    with right:
        st.markdown(
            """
            <div class="login-brand">
                <div class="brand-mark">N</div>
                <div class="eyebrow">A BETTER WAY TO GET ANSWERS</div>
                <h1>Good work starts<br><span>with clarity.</span></h1>
                <p>Get helpful, grounded answers about the policies and resources
                that make your workplace work.</p>
                <div class="login-proof"><span>✓</span> Company knowledge, not guesswork</div>
                <div class="login-proof"><span>✓</span> Sources and reasoning in view</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
else:
    render_sidebar()
    st.markdown(
        '<div class="page-kicker">YOUR WORKPLACE, MADE CLEAR</div>'
        '<h1 class="workspace-title">NexaHR Employee Support</h1>'
        '<div class="workspace-subtitle">Ask a question. Get a clear, grounded answer.</div>',
        unsafe_allow_html=True,
    )

    try:
        check_health()
        st.markdown(
            '<div class="panel-caption">● Connected to your HR support workspace</div>',
            unsafe_allow_html=True,
        )
    except requests.RequestException:
        st.warning(
            "The NexaHR API is not reachable. Start the FastAPI backend and check "
            "API_BASE_URL in .env."
        )

    chat_column, workflow_column = st.columns([0.69, 0.31], gap="large")
    with chat_column:
        st.markdown(
            '<div class="chat-intro"><div class="chat-intro-title">'
            'How can we help you today?</div><div class="chat-intro-copy">'
            'Ask about workplace policies, leave, benefits, payroll, or getting support. '
            'Answers are grounded in available evidence.</div></div>',
            unsafe_allow_html=True,
        )
        render_chat_history()
        question = st.chat_input("Ask NexaHR about a policy or workplace question")

    with workflow_column:
        workflow_panel = st.empty()
        previous_events = st.session_state.get("last_events", [])
        render_workflow_panel(workflow_panel, previous_events, running=False)

    if question:
        st.session_state.setdefault("messages", []).append(
            {"role": "user", "content": question}
        )
        with chat_column:
            with st.chat_message("user"):
                st.markdown(question)
        consume_chat(question, workflow_panel)
        st.rerun()
