import hmac

import streamlit as st

from frontend.config import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    DEMO_EMPLOYEE_LOGIN_ENABLED,
    DEMO_EMPLOYEE_PASSWORD,
    DEMO_EMPLOYEE_USERNAME,
    EMPLOYEE_PASSWORD,
    EMPLOYEE_USERNAME,
)

ROLE_CREDENTIALS = {
    "Admin": (ADMIN_USERNAME, ADMIN_PASSWORD),
    "Employee": (EMPLOYEE_USERNAME, EMPLOYEE_PASSWORD),
}


def credentials_configured(role: str) -> bool:
    username, password = ROLE_CREDENTIALS[role]
    configured_credentials = bool(username and password)
    demo_credentials = role == "Employee" and DEMO_EMPLOYEE_LOGIN_ENABLED
    return configured_credentials or demo_credentials


def authenticate(role: str, username: str, password: str) -> bool:
    configured_username, configured_password = ROLE_CREDENTIALS[role]
    configured_match = bool(configured_username and configured_password) and (
        hmac.compare_digest(
            username.encode("utf-8"), configured_username.encode("utf-8")
        )
        and hmac.compare_digest(
            password.encode("utf-8"), configured_password.encode("utf-8")
        )
    )
    demo_match = (
        role == "Employee"
        and DEMO_EMPLOYEE_LOGIN_ENABLED
        and hmac.compare_digest(
            username.encode("utf-8"), DEMO_EMPLOYEE_USERNAME.encode("utf-8")
        )
        and hmac.compare_digest(
            password.encode("utf-8"), DEMO_EMPLOYEE_PASSWORD.encode("utf-8")
        )
    )
    return configured_match or demo_match


def render_login() -> None:
    st.markdown(
        """
        <div class="login-brand">
            <div class="brand-mark">N</div>
            <div class="eyebrow">YOUR WORKPLACE, MADE CLEAR</div>
            <h1>People-first support.<br><span>Grounded in your policies.</span></h1>
            <p>One trusted place to find answers, understand workplace policies,
            and help your people do their best work.</p>
            <div class="login-proof">
                <span>✦</span> Answers grounded in your company knowledge
            </div>
            <div class="login-proof">
                <span>⌘</span> Thoughtful AI, with its sources in view
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Welcome to NexaHR")
    st.caption("Sign in to your workspace to continue.")

    role = st.radio(
        "Choose your workspace",
        options=["Admin", "Employee"],
        format_func=lambda value: (
            "HR / MANAGEMENT" if value == "Admin" else "EMPLOYEE"
        ),
        horizontal=True,
        label_visibility="collapsed",
        key="login_role",
    )

    if not credentials_configured(role):
        prefix = "NEXAHR_ADMIN" if role == "Admin" else "NEXAHR_EMPLOYEE"
        st.error(
            f"{role} sign-in is not configured. Set {prefix}_USERNAME and "
            f"{prefix}_PASSWORD in the project .env file."
        )
    if role == "Employee" and DEMO_EMPLOYEE_LOGIN_ENABLED:
        st.info(
            "Development demo login: username `emp1` · password `emp1-demo`. "
            "Configure NEXAHR_EMPLOYEE_USERNAME and NEXAHR_EMPLOYEE_PASSWORD "
            "in .env to use your own credentials."
        )

    with st.form("login-form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your password",
        )
        submitted = st.form_submit_button(
            "Sign in to NexaHR",
            use_container_width=True,
            disabled=not credentials_configured(role),
        )

    if submitted:
        if authenticate(role, username, password):
            st.session_state["authenticated"] = True
            st.session_state["role"] = role
            st.session_state["username"] = username
            st.session_state["messages"] = []
            st.session_state["last_trace"] = []
            st.session_state["last_events"] = []
            st.session_state["last_source"] = ""
            st.rerun()
        else:
            st.error("Those credentials don't match this workspace.")

    st.markdown(
        '<div class="login-footnote">Secure access for your organization</div>',
        unsafe_allow_html=True,
    )
