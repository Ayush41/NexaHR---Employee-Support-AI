import requests
import streamlit as st

from frontend import api, config
from frontend.session import start_session


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
    st.caption("Sign in to your workspace or request an employee account.")
    login_tab, register_tab = st.tabs(["Sign in", "Create employee account"])

    with login_tab:
        with st.form("login-form"):
            identifier = st.text_input(
                "Work email or employee ID",
                placeholder="name@company.com",
                autocomplete="username",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                autocomplete="current-password",
            )
            submitted = st.form_submit_button(
                "Sign in to NexaHR",
                type="primary",
                use_container_width=True,
            )
        if submitted:
            try:
                start_session(api.login(identifier, password))
            except (requests.RequestException, RuntimeError, ValueError, KeyError) as exc:
                st.error(str(exc))

        if config.APP_ENV not in {"prod", "production"}:
            st.info("Local demo employee: `emp1` · password `emp1-demo`.")
        st.caption(
            "HR/Admin accounts use this same sign-in and must be provisioned by "
            "the backend operator. Employee registration cannot grant admin access."
        )

    with register_tab:
        st.caption("New registrations remain pending until an administrator approves them.")
        with st.form("employee-registration-form"):
            full_name = st.text_input("Full name")
            email = st.text_input("Work email", placeholder="name@company.com")
            employee_id = st.text_input("Employee ID")
            left, right = st.columns(2)
            with left:
                job_title = st.text_input("Job title")
                department = st.text_input("Department")
                password = st.text_input(
                    "Create password",
                    type="password",
                    help="Use at least 10 characters.",
                )
            with right:
                location = st.text_input("Location")
                manager = st.text_input("Manager")
                confirm_password = st.text_input(
                    "Confirm password",
                    type="password",
                )
            submitted = st.form_submit_button(
                "Submit registration",
                type="primary",
                use_container_width=True,
            )
        if submitted:
            if password != confirm_password:
                st.error("The passwords do not match.")
            else:
                try:
                    result = api.register_employee(
                        {
                            "email": email,
                            "password": password,
                            "employee_id": employee_id,
                            "full_name": full_name,
                            "job_title": job_title,
                            "department": department,
                            "location": location,
                            "manager": manager,
                        }
                    )
                    st.success(result["message"])
                except (
                    requests.RequestException,
                    RuntimeError,
                    ValueError,
                    KeyError,
                ) as exc:
                    st.error(str(exc))

    st.markdown(
        '<div class="login-footnote">Role-based access is enforced by the NexaHR API</div>',
        unsafe_allow_html=True,
    )
