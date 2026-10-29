import hmac
import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_USERNAME = os.getenv("NEXAHR_ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("NEXAHR_ADMIN_PASSWORD", "")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

st.set_page_config(page_title="NexaHR", page_icon="N", layout="wide")


def show_login() -> None:
    st.title("NexaHR")
    st.subheader("Admin sign in")
    st.write("Sign in to chat with the HR assistant and manage policy documents.")

    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        st.error(
            "Admin sign-in is not configured. Set NEXAHR_ADMIN_USERNAME and "
            "NEXAHR_ADMIN_PASSWORD in the project .env file, then restart Streamlit."
        )
        return

    with st.form("admin-login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)

    if submitted:
        username_matches = hmac.compare_digest(username, ADMIN_USERNAME)
        password_matches = hmac.compare_digest(password, ADMIN_PASSWORD)
        if username_matches and password_matches:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid username or password.")


def api_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Backend returned HTTP {response.status_code}."

    detail = payload.get("detail", payload.get("message"))
    if isinstance(detail, str) and detail:
        return detail
    return f"Backend returned HTTP {response.status_code}."


def show_admin_app() -> None:
    with st.sidebar:
        st.title("NexaHR")
        st.caption("Signed in as admin")
        if st.button("Sign out", use_container_width=True):
            st.session_state.clear()
            st.rerun()

        st.divider()
        st.subheader("Policy documents")
        uploaded_file = st.file_uploader(
            "Choose a PDF, DOCX, TXT, or Markdown file",
            type=["pdf", "docx", "txt", "md"],
        )
        if st.button(
            "Upload and index",
            disabled=uploaded_file is None,
            use_container_width=True,
        ):
            if not ADMIN_API_KEY or ADMIN_API_KEY == "change-me-in-production":
                st.error("Set a non-default ADMIN_API_KEY in the project .env file.")
            else:
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/api/ingest",
                        headers={"x-admin-key": ADMIN_API_KEY},
                        files={
                            "file": (
                                uploaded_file.name,
                                uploaded_file.getvalue(),
                                uploaded_file.type or "application/octet-stream",
                            )
                        },
                        timeout=300,
                    )
                    if not response.ok:
                        st.error(api_error_message(response))
                    else:
                        result = response.json()
                        st.success(
                            f"Indexed {result['file']} ({result['chunks']} chunks)."
                        )
                except requests.RequestException as exc:
                    st.error(f"Could not reach the NexaHR API: {exc}")

    st.title("NexaHR Employee Support")
    try:
        health = requests.get(f"{API_BASE_URL}/api/health", timeout=5)
        health.raise_for_status()
        st.caption(f"Backend: {health.json().get('status', 'connected')}")
    except requests.RequestException:
        st.warning(
            "The NexaHR API is not reachable. Start the FastAPI backend and check "
            "API_BASE_URL in .env."
        )

    for message in st.session_state.get("messages", []):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("citations"):
                with st.expander("Sources"):
                    for citation in message["citations"]:
                        title = citation.get("title", "Reference")
                        url = citation.get("url")
                        st.markdown(f"- [{title}]({url})" if url else f"- {title}")
            if message.get("trace"):
                with st.expander("Agent execution trace"):
                    for step in message["trace"]:
                        st.markdown(f"- {step}")

    question = st.chat_input("Ask about company policies, leave, benefits, or work")
    if question:
        st.session_state.setdefault("messages", []).append(
            {"role": "user", "content": question}
        )
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("NexaHR is preparing an answer..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/api/chat",
                        json={"question": question},
                        timeout=180,
                    )
                    if not response.ok:
                        answer = f"Request failed: {api_error_message(response)}"
                        st.error(answer)
                        st.session_state["messages"].append(
                            {"role": "assistant", "content": answer}
                        )
                    else:
                        result = response.json()
                        answer = result.get("answer", "The API returned no answer.")
                        st.markdown(answer)
                        citations = result.get("citations", [])
                        trace = result.get("trace", [])
                        if citations:
                            with st.expander("Sources"):
                                for citation in citations:
                                    title = citation.get("title", "Reference")
                                    url = citation.get("url")
                                    st.markdown(
                                        f"- [{title}]({url})" if url else f"- {title}"
                                    )
                        if trace:
                            with st.expander("Agent execution trace"):
                                for step in trace:
                                    st.markdown(f"- {step}")
                        st.session_state["messages"].append(
                            {
                                "role": "assistant",
                                "content": answer,
                                "citations": citations,
                                "trace": trace,
                            }
                        )
                except requests.RequestException as exc:
                    answer = f"Could not reach the NexaHR API: {exc}"
                    st.error(answer)
                    st.session_state["messages"].append(
                        {"role": "assistant", "content": answer}
                    )


if not st.session_state.get("authenticated", False):
    show_login()
else:
    show_admin_app()
