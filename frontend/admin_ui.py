from datetime import date

import requests
import streamlit as st

from frontend import api


def _show_request_error(exc: Exception) -> None:
    st.error(str(exc))


def _registration_card(registration: dict) -> None:
    employee = registration.get("employee") or {}
    with st.container(border=True):
        st.markdown(f"**{employee.get('full_name', 'Name not provided')}**")
        st.caption(
            f"{registration['email']} · ID {employee.get('employee_id', 'not provided')}"
        )
        st.write(
            f"{employee.get('job_title') or 'Title not provided'} · "
            f"{employee.get('department') or 'Department not provided'} · "
            f"{employee.get('location') or 'Location not provided'}"
        )
        approve, reject = st.columns(2)
        if approve.button(
            "Approve account",
            key=f"approve-registration-{registration['id']}",
            type="primary",
            use_container_width=True,
        ):
            try:
                api.approve_registration(
                    st.session_state["access_token"], registration["id"]
                )
                st.success("Employee account approved.")
                st.rerun()
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                _show_request_error(exc)
        if reject.button(
            "Reject registration",
            key=f"reject-registration-{registration['id']}",
            use_container_width=True,
        ):
            try:
                api.reject_registration(
                    st.session_state["access_token"], registration["id"]
                )
                st.success("Pending registration removed.")
                st.rerun()
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                _show_request_error(exc)


def _render_registrations() -> None:
    st.markdown("#### Registration approvals")
    try:
        registrations = api.list_pending_registrations(
            st.session_state["access_token"]
        )
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        _show_request_error(exc)
        return
    if not registrations:
        st.info("There are no employee registrations waiting for approval.")
        return
    for registration in registrations:
        _registration_card(registration)


def _render_employee_directory() -> None:
    st.markdown("#### Employee directory")
    try:
        employees = api.list_employees(st.session_state["access_token"])
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        _show_request_error(exc)
        return
    if not employees:
        st.info("No employee accounts yet. Create an account in the Add employee tab.")
        return

    st.dataframe(
        [
            {
                "Name": (record.get("employee") or {}).get("full_name", ""),
                "Employee ID": (record.get("employee") or {}).get("employee_id", ""),
                "Email": record["email"],
                "Department": (record.get("employee") or {}).get("department", ""),
                "Account": record["status"],
            }
            for record in employees
        ],
        hide_index=True,
        use_container_width=True,
    )
    choices = {record["id"]: record for record in employees}
    selected_id = st.selectbox(
        "Select an employee to manage",
        options=list(choices),
        format_func=lambda user_id: (
            f"{choices[user_id].get('employee', {}).get('full_name', 'Employee')} "
            f"({choices[user_id].get('employee', {}).get('employee_id', user_id)})"
        ),
    )
    selected = choices[selected_id]
    profile = selected.get("employee") or {}
    leave = profile.get("leave") or {}

    with st.form(f"edit-employee-{selected_id}"):
        st.markdown("##### Profile and leave balance")
        left, right = st.columns(2)
        with left:
            email = st.text_input("Work email", value=selected["email"])
            full_name = st.text_input("Full name", value=profile.get("full_name", ""))
            employee_id = st.text_input(
                "Employee ID", value=profile.get("employee_id", "")
            )
            job_title = st.text_input("Job title", value=profile.get("job_title", ""))
        with right:
            department = st.text_input(
                "Department", value=profile.get("department", "")
            )
            location = st.text_input("Location", value=profile.get("location", ""))
            manager = st.text_input("Manager", value=profile.get("manager", ""))
            annual_days = st.number_input(
                "Annual leave days",
                min_value=0.0,
                value=float(leave.get("annual_leave_days", 20)),
                step=0.5,
            )
            used_days = st.number_input(
                "Leave days used",
                min_value=0.0,
                value=float(leave.get("leave_days_used", 0)),
                step=0.5,
            )
        submitted = st.form_submit_button(
            "Save employee changes",
            type="primary",
            use_container_width=True,
        )
    if submitted:
        try:
            api.update_employee(
                st.session_state["access_token"],
                selected_id,
                {
                    "email": email,
                    "full_name": full_name,
                    "employee_id": employee_id,
                    "job_title": job_title,
                    "department": department,
                    "location": location,
                    "manager": manager,
                    "annual_leave_days": annual_days,
                    "leave_days_used": used_days,
                },
            )
            st.success("Employee record updated.")
            st.rerun()
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            _show_request_error(exc)

    if selected["status"] == "active":
        if st.button("Deactivate employee account", key=f"deactivate-{selected_id}"):
            try:
                api.deactivate_employee(
                    st.session_state["access_token"], selected_id
                )
                st.success("Account deactivated. Its history has been retained.")
                st.rerun()
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                _show_request_error(exc)
    elif selected["status"] == "disabled":
        if st.button("Reactivate employee account", key=f"reactivate-{selected_id}"):
            try:
                api.reactivate_employee(
                    st.session_state["access_token"], selected_id
                )
                st.success("Employee account reactivated.")
                st.rerun()
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                _show_request_error(exc)

    if selected["status"] != "active":
        return

    st.divider()
    st.markdown("##### Attendance")
    with st.form(f"attendance-form-{selected_id}"):
        attendance_date = st.date_input("Record date", value=date.today())
        attendance_status = st.selectbox(
            "Status", ["present", "absent", "remote", "leave"]
        )
        attendance_note = st.text_input("Note (optional)")
        add_attendance = st.form_submit_button("Add attendance record")
    if add_attendance:
        try:
            api.add_attendance_record(
                st.session_state["access_token"],
                selected_id,
                {
                    "record_date": attendance_date.isoformat(),
                    "status": attendance_status,
                    "note": attendance_note,
                },
            )
            st.success("Attendance record added.")
            st.rerun()
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            _show_request_error(exc)
    for row in profile.get("attendance", []):
        columns = st.columns([2, 2, 4, 1])
        columns[0].write(row["record_date"])
        columns[1].write(row["status"])
        columns[2].write(row.get("note", ""))
        if columns[3].button("Delete", key=f"delete-attendance-{row['id']}"):
            try:
                api.delete_attendance_record(
                    st.session_state["access_token"], selected_id, row["id"]
                )
                st.rerun()
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                _show_request_error(exc)

    st.divider()
    st.markdown("##### Benefits")
    with st.form(f"benefit-form-{selected_id}"):
        benefit_name = st.text_input("Benefit name")
        benefit_status = st.selectbox(
            "Enrollment status",
            ["enrolled", "eligible", "not_enrolled", "pending"],
        )
        benefit_note = st.text_input("Note (optional)")
        add_benefit = st.form_submit_button("Add benefit record")
    if add_benefit:
        try:
            api.add_benefit_record(
                st.session_state["access_token"],
                selected_id,
                {
                    "benefit_name": benefit_name,
                    "enrollment_status": benefit_status,
                    "note": benefit_note,
                },
            )
            st.success("Benefit record added.")
            st.rerun()
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            _show_request_error(exc)
    for row in profile.get("benefits", []):
        columns = st.columns([3, 2, 4, 1])
        columns[0].write(row["benefit_name"])
        columns[1].write(row["enrollment_status"])
        columns[2].write(row.get("note", ""))
        if columns[3].button("Delete", key=f"delete-benefit-{row['id']}"):
            try:
                api.delete_benefit_record(
                    st.session_state["access_token"], selected_id, row["id"]
                )
                st.rerun()
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                _show_request_error(exc)


def _render_create_employee() -> None:
    st.markdown("#### Add an employee account")
    st.caption(
        "The employee will be asked to change this temporary password after signing in."
    )
    with st.form("create-employee-form"):
        left, right = st.columns(2)
        with left:
            full_name = st.text_input("Full name", key="new-employee-name")
            email = st.text_input("Work email", key="new-employee-email")
            employee_id = st.text_input("Employee ID", key="new-employee-id")
            job_title = st.text_input("Job title", key="new-employee-title")
            department = st.text_input("Department", key="new-employee-department")
        with right:
            location = st.text_input("Location", key="new-employee-location")
            manager = st.text_input("Manager", key="new-employee-manager")
            annual_days = st.number_input(
                "Annual leave days", min_value=0.0, value=20.0, step=0.5
            )
            used_days = st.number_input(
                "Leave days used", min_value=0.0, value=0.0, step=0.5
            )
            password = st.text_input(
                "Temporary password",
                type="password",
                help="Use at least 10 characters and share it securely.",
            )
            confirm_password = st.text_input(
                "Confirm temporary password", type="password"
            )
        submitted = st.form_submit_button(
            "Create employee account",
            type="primary",
            use_container_width=True,
        )
    if not submitted:
        return
    if password != confirm_password:
        st.error("The temporary passwords do not match.")
        return
    try:
        api.create_employee(
            st.session_state["access_token"],
            {
                "email": email,
                "password": password,
                "employee_id": employee_id,
                "full_name": full_name,
                "job_title": job_title,
                "department": department,
                "location": location,
                "manager": manager,
                "annual_leave_days": annual_days,
                "leave_days_used": used_days,
            },
        )
        st.success(
            "Employee account created. They must change the temporary password at first sign-in."
        )
        st.rerun()
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        _show_request_error(exc)


def render_admin_workspace() -> None:
    st.markdown("## Employee administration")
    st.caption(
        "Manage registrations, employee records, leave balances, attendance, and benefits."
    )
    directory_tab, approvals_tab, create_tab = st.tabs(
        ["Employee directory", "Pending approvals", "Add employee"]
    )
    with directory_tab:
        _render_employee_directory()
    with approvals_tab:
        _render_registrations()
    with create_tab:
        _render_create_employee()
