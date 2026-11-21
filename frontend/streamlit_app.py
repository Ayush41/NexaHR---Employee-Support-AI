import sys
from pathlib import Path
from typing import Any

import requests
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend import api
from frontend.admin_ui import render_admin_workspace
from frontend.auth import render_login
from frontend.employee_ui import render_employee_dashboard
from frontend.session import start_session
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


def _clear_session() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def _render_password_change() -> None:
    st.markdown("## Set your password")
    st.info("Your administrator created a temporary password. Change it to continue.")
    with st.form("required-password-change"):
        current_password = st.text_input("Temporary password", type="password")
        new_password = st.text_input(
            "New password",
            type="password",
            help="Use at least 10 characters.",
        )
        confirm_password = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button(
            "Update password", type="primary", use_container_width=True
        )
    if not submitted:
        return
    if new_password != confirm_password:
        st.error("The new passwords do not match.")
        return
    try:
        result = api.change_password(
            st.session_state["access_token"],
            current_password,
            new_password,
        )
        start_session(result)
    except (requests.RequestException, RuntimeError, ValueError, KeyError) as exc:
        st.error(str(exc))


def consume_chat(question: str, workflow_panel: Any) -> None:
    events: list[dict] = []
    result: dict = {}
    st.session_state["last_source"] = ""
    st.session_state["last_trace"] = []
    st.session_state["last_events"] = []

    with st.chat_message("assistant"):
        answer_placeholder = st.empty()
        answer_placeholder.markdown(
            '<span class="panel-caption">Following the LangGraph workflow…</span>',
            unsafe_allow_html=True,
        )
        try:
            for event in api.stream_chat(
                question, st.session_state["access_token"]
            ):
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
                    raise RuntimeError(
                        event.get("message", "The chat request failed.")
                    )

            if not result:
                raise RuntimeError(
                    "The chat stream ended before returning an answer."
                )

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
        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            OSError,
        ) as exc:
            answer_placeholder.error(str(exc))
            st.session_state.setdefault("messages", []).append(
                {"role": "assistant", "content": str(exc)}
            )
    if events:
        render_workflow_panel(workflow_panel, events, running=False)


def render_workspace() -> None:
    render_sidebar()
    role = st.session_state["role"]

    if role == "Admin":
        render_admin_workspace()
    else:
        render_employee_dashboard()

    st.markdown(
        '<div class="page-kicker">YOUR WORKPLACE, MADE CLEAR</div>'
        '<h1 class="workspace-title">NexaHR Employee Support</h1>'
        '<div class="workspace-subtitle">Ask a question. Get a clear, grounded answer.</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="panel-caption">● Connected to your HR support workspace</div>',
        unsafe_allow_html=True,
    )

    chat_column, workflow_column = st.columns([0.69, 0.31], gap="large")
    with chat_column:
        st.markdown(
            '<div class="chat-intro"><div class="chat-intro-title">'
            'How can we help you today?</div><div class="chat-intro-copy">'
            'Ask about workplace policies or your own profile, leave, attendance, '
            'and benefits. Personal records are read from your authorized account.</div></div>',
            unsafe_allow_html=True,
        )
        render_chat_history()
        question = st.chat_input("Ask NexaHR about a policy or your own HR records")

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


auth_notice = st.session_state.pop("auth_notice", "")
if not st.session_state.get("authenticated", False):
    if auth_notice:
        st.info(auth_notice)
    st.markdown(
        '<div class="page-kicker">NEXAHR · EMPLOYEE SUPPORT</div>',
        unsafe_allow_html=True,
    )
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
    try:
        account = api.get_account(st.session_state["access_token"])
        st.session_state["account"] = account
        st.session_state["role"] = account["role"].title()
        if account["must_change_password"]:
            _render_password_change()
        else:
            render_workspace()
    except api.AuthenticationError:
        _clear_session()
        st.session_state["auth_notice"] = "Your sign-in expired. Please sign in again."
        st.rerun()
    except (requests.RequestException, RuntimeError, ValueError, KeyError) as exc:
        st.error(f"Could not verify your account with the backend: {exc}")
