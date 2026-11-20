import requests
import streamlit as st

from frontend import api


def render_employee_dashboard() -> None:
    try:
        account = api.get_my_employee_record(st.session_state["access_token"])
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        st.error(str(exc))
        return

    employee = account.get("employee")
    if not employee:
        st.info("Your employee profile is not available yet. Contact HR.")
        return

    st.markdown("## Your employee record")
    st.caption("Personal records shown here are available only to your account.")
    if employee.get("is_demo"):
        st.info("This is sample demonstration data, not an official HR record.")

    leave = employee.get("leave") or {}
    remaining = leave.get("annual_leave_days", 0) - leave.get("leave_days_used", 0)
    columns = st.columns(4)
    columns[0].metric("Employee ID", employee["employee_id"])
    columns[1].metric("Leave available", f"{remaining:g} days")
    columns[2].metric("Attendance records", len(employee.get("attendance", [])))
    columns[3].metric("Benefit records", len(employee.get("benefits", [])))

    with st.expander("Profile details", expanded=True):
        left, right = st.columns(2)
        with left:
            st.write(f"**Name:** {employee['full_name']}")
            st.write(f"**Job title:** {employee.get('job_title') or 'Not provided'}")
            st.write(f"**Department:** {employee.get('department') or 'Not provided'}")
        with right:
            st.write(f"**Location:** {employee.get('location') or 'Not provided'}")
            st.write(f"**Manager:** {employee.get('manager') or 'Not provided'}")
            st.write(f"**Work email:** {account['email']}")
        if leave:
            st.caption(
                f"Leave balance: {leave['leave_days_used']:g} of "
                f"{leave['annual_leave_days']:g} days used"
                + (f" · updated {leave['as_of']}" if leave.get("as_of") else "")
            )

    attendance = employee.get("attendance", [])
    benefits = employee.get("benefits", [])
    detail_tabs = st.tabs(["Attendance", "Benefits"])
    with detail_tabs[0]:
        if attendance:
            st.dataframe(
                [
                    {
                        "Date": row["record_date"],
                        "Status": row["status"],
                        "Note": row.get("note", ""),
                    }
                    for row in attendance
                ],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.caption("No attendance records have been added yet.")
    with detail_tabs[1]:
        if benefits:
            st.dataframe(
                [
                    {
                        "Benefit": row["benefit_name"],
                        "Enrollment": row["enrollment_status"],
                        "Note": row.get("note", ""),
                    }
                    for row in benefits
                ],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.caption("No personal benefit enrollment records have been added yet.")
