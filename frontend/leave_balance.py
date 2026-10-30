import json
import math
import re
from pathlib import Path
from typing import Any

from frontend.config import ROOT_DIR

LEAVE_TERMS = re.compile(r"\b(?:leave|leaves|pto)\b", re.IGNORECASE)
BALANCE_INTENT = re.compile(
    r"\b(?:left|remaining|balance|available|unused)\b"
    r"|\bhow many\b.*\b(?:leave|leaves|pto)\b.*\b(?:can|could|may)\b"
    r"|\b(?:can|could|may)\s+i\s+(?:apply|take)\b.*\b(?:leave|pto)\b",
    re.IGNORECASE,
)
RECORDS_PATH = Path(ROOT_DIR) / "frontend" / "data" / "employee_leave_balances.json"


def is_leave_balance_question(question: str) -> bool:
    return bool(LEAVE_TERMS.search(question) and BALANCE_INTENT.search(question))


def load_employee_leave_record(employee_id: str) -> dict[str, Any] | None:
    with RECORDS_PATH.open(encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, dict):
        raise ValueError(f"{RECORDS_PATH} must contain an employee ID to record mapping.")

    record = next(
        (
            value
            for key, value in records.items()
            if key.casefold() == employee_id.casefold()
        ),
        None,
    )
    if record is None:
        return None
    if not isinstance(record, dict):
        raise ValueError(f"Leave record for {employee_id!r} must be a JSON object.")

    entitlement = record.get("annual_leave_days")
    used = record.get("leave_days_used")
    if (
        isinstance(entitlement, bool)
        or not isinstance(entitlement, (int, float))
        or isinstance(used, bool)
        or not isinstance(used, (int, float))
        or not math.isfinite(entitlement)
        or not math.isfinite(used)
        or entitlement < 0
        or used < 0
        or used > entitlement
    ):
        raise ValueError(
            f"Leave record for {employee_id!r} must have non-negative numeric "
            "annual_leave_days and leave_days_used, with used days not exceeding entitlement."
        )

    return {
        "employee_id": str(record.get("job_id", employee_id)),
        "full_name": str(record.get("full_name", employee_id)),
        "job_title": str(record.get("job_title", "Not provided")),
        "department": str(record.get("department", "Not provided")),
        "location": str(record.get("location", "Not provided")),
        "manager": str(record.get("manager", "Not provided")),
        "annual_leave_days": entitlement,
        "leave_days_used": used,
        "leave_days_remaining": entitlement - used,
        "as_of": record.get("as_of", ""),
        "demo_record": bool(record.get("demo_record", False)),
    }


def answer_leave_balance_question(
    question: str, employee_id: str
) -> dict[str, Any] | None:
    if not is_leave_balance_question(question):
        return None

    record = load_employee_leave_record(employee_id)
    if record is None:
        answer = (
            "I couldn't find a leave-balance record for your signed-in account. "
            "Please contact HR to confirm your current balance."
        )
        trace = [
            "Router → PERSONAL LEAVE BALANCE",
            "Employee leave record → no record found for signed-in account",
            "Answer generation → LEAVE RECORD NOT FOUND",
        ]
    else:
        demo_notice = (
            " This is sample demonstration data, not an official HR balance."
            if record["demo_record"]
            else ""
        )
        as_of = f" (record as of {record['as_of']})" if record["as_of"] else ""
        answer = (
            f"You have **{record['leave_days_remaining']:g} of "
            f"{record['annual_leave_days']:g} annual leave days available to request**. "
            f"You have used {record['leave_days_used']:g} days{as_of}. "
            "Requests remain subject to your company's leave policy and approval."
            f"{demo_notice}"
        )
        trace = [
            "Router → PERSONAL LEAVE BALANCE",
            f"Employee leave record → {employee_id}",
            (
                f"Leave balance → {record['leave_days_remaining']:g} available "
                f"of {record['annual_leave_days']:g} days "
                f"({record['leave_days_used']:g} used)"
            ),
            "Answer generation → EMPLOYEE LEAVE RECORDS",
        ]

    return {
        "answer": answer,
        "source_used": "employee_leave_records",
        "trace": trace,
        "citations": [],
        "current_query": question,
        "events": [
            {
                "type": "step",
                "node": "route_question",
                "data": {"source_used": "employee_leave_records", "trace": trace[:1]},
            },
            {
                "type": "step",
                "node": "employee_leave_balance",
                "data": {"trace": trace[1:]},
            },
        ],
    }
