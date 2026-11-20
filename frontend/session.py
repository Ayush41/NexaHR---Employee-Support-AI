import streamlit as st


def start_session(result: dict) -> None:
    account = result["account"]
    st.session_state["authenticated"] = True
    st.session_state["access_token"] = result["access_token"]
    st.session_state["role"] = account["role"].title()
    st.session_state["username"] = account["username"]
    st.session_state["account"] = account
    st.session_state["messages"] = []
    st.session_state["last_trace"] = []
    st.session_state["last_events"] = []
    st.session_state["last_source"] = ""
    st.rerun()
