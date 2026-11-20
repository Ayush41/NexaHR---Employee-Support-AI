import re

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import EmployeeProfile, User

LEAVE_TERM_PATTERN = (
    r"(?:leave|leaves|pto|paid\s+time\s+off|time\s+off|vacation|days?\s+off)"
)
LEAVE_TERMS = re.compile(rf"\b{LEAVE_TERM_PATTERN}\b", re.IGNORECASE)
ATTENDANCE_TERMS = re.compile(
    r"\b(?:attendance|absen(?:ce|ces|t)|present|late)\b", re.IGNORECASE
)
BENEFIT_TERMS = re.compile(
    r"\b(?:benefit|benefits|insurance|enrollment|enrolled)\b", re.IGNORECASE
)
PROFILE_TERMS = re.compile(
    r"\b(?:profile|job title|role|department|manager|location|employee id|employee number)\b",
    re.IGNORECASE,
)
PERSONAL_LEAVE_QUESTION = re.compile(
    rf"\b(?:my|mine)\b.*\b{LEAVE_TERM_PATTERN}\b.*"
    r"\b(?:left|remaining|balance|available|allowance|entitlement|used)\b"
    r"|\b(?:how many|how much|what(?:'s| is))\b.*"
    rf"\b{LEAVE_TERM_PATTERN}\b.*"
    r"\b(?:do i have|have i|i have|left|remaining|balance|available|"
    r"allowance|entitlement|used|accrued)\b"
    rf"|\b(?:do i have|have i|am i entitled to)\b.*\b{LEAVE_TERM_PATTERN}\b.*"
    r"\b(?:left|remaining|balance|available|used|accrued)\b",
    re.IGNORECASE,
)
PERSONAL_BENEFIT_QUESTION = re.compile(
    r"\b(?:what|which|am i)\b.*\b(?:benefit|benefits|insurance|enrolled)\b",
    re.IGNORECASE,
)


def _intent(question: str) -> str | None:
    has_my = bool(re.search(r"\bmy\b", question, re.IGNORECASE))
    if LEAVE_TERMS.search(question) and PERSONAL_LEAVE_QUESTION.search(question):
        return "leave"
    if ATTENDANCE_TERMS.search(question) and has_my:
        return "attendance"
    if BENEFIT_TERMS.search(question) and (
        has_my or PERSONAL_BENEFIT_QUESTION.search(question)
    ):
        return "benefits"
    if PROFILE_TERMS.search(question) and has_my:
        return "profile"
    return None


def answer_personal_question(
    db: Session, user: User, question: str
) -> dict | None:
    intent = _intent(question)
    if intent is None:
        return None

    profile_query = select(EmployeeProfile).where(EmployeeProfile.user_id == user.id)
    if intent == "leave":
        profile_query = profile_query.options(
            joinedload(EmployeeProfile.leave_balance)
        )
    elif intent == "attendance":
        profile_query = profile_query.options(
            selectinload(EmployeeProfile.attendance_records)
        )
    elif intent == "benefits":
        profile_query = profile_query.options(selectinload(EmployeeProfile.benefits))
    profile = db.scalar(profile_query)
    if profile is None:
        return _result(
            "I couldn't find an employee record for your account. Please contact HR.",
            ["Router → PERSONAL EMPLOYEE RECORDS", "Employee record → not found"],
        )

    if intent == "leave":
        leave = profile.leave_balance
        if leave is None:
            answer = "Your leave balance has not been added yet. Please contact HR."
            trace = ["Router → PERSONAL LEAVE RECORDS", "Leave record → not available"]
        else:
            remaining = leave.annual_leave_days - leave.leave_days_used
            if profile.is_demo:
                answer = (
                    f"You have **{remaining:g} of {leave.annual_leave_days:g} annual "
                    f"leave days available**; {leave.leave_days_used:g} days are recorded "
                    "as used. This is sample demonstration data, not an official balance."
                )
            else:
                answer = (
                    f"You have **{remaining:g} of {leave.annual_leave_days:g} annual "
                    f"leave days available**; {leave.leave_days_used:g} days are "
                    "recorded as used. Requests remain subject to company policy "
                    "and approval."
                )
            trace = [
                "Router → PERSONAL LEAVE RECORDS",
                f"Employee record → {profile.employee_id}",
                "Answer generation → authorized employee database record",
            ]
        return _result(answer, trace)

    if intent == "attendance":
        rows = sorted(
            profile.attendance_records,
            key=lambda row: (row.record_date, row.id),
            reverse=True,
        )
        if not rows:
            answer = "There are no attendance records available for your account yet."
        else:
            counts: dict[str, int] = {}
            for row in rows:
                counts[row.status] = counts.get(row.status, 0) + 1
            summary = ", ".join(
                f"{count} {name}" for name, count in sorted(counts.items())
            )
            answer = (
                f"Your attendance records show {summary} across "
                f"{len(rows)} recorded days."
            )
        return _result(
            answer,
            [
                "Router → PERSONAL ATTENDANCE",
                f"Attendance records → {len(rows)}",
            ],
        )

    if intent == "benefits":
        records = profile.benefits
        if records:
            details = "; ".join(
                f"{item.benefit_name}: {item.enrollment_status}"
                for item in sorted(records, key=lambda row: row.benefit_name.casefold())
            )
            answer = f"Your recorded benefit enrollments: {details}."
        else:
            answer = (
                "No personal benefit enrollment records are available for your "
                "account yet. General benefit information may be available in the "
                "company policy knowledge base."
            )
        return _result(
            answer,
            ["Router → PERSONAL BENEFITS", f"Benefit records → {len(records)}"],
        )

    answer = (
        f"Your profile: **{profile.full_name}** (employee ID {profile.employee_id}), "
        f"{profile.job_title or 'job title not provided'} in "
        f"{profile.department or 'department not provided'}. "
        f"Location: {profile.location or 'not provided'}. "
        f"Manager: {profile.manager or 'not provided'}."
    )
    return _result(
        answer,
        [
            "Router → PERSONAL EMPLOYEE PROFILE",
            "Answer generation → authorized employee profile",
        ],
    )


def _result(answer: str, trace: list[str]) -> dict:
    return {
        "answer": answer,
        "source_used": "employee_records",
        "trace": trace,
        "citations": [],
        "current_query": "",
    }
