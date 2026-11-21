import json
from collections.abc import Iterator
from typing import Any

import requests

from frontend.config import API_BASE_URL


class AuthenticationError(RuntimeError):
    pass


def error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Backend returned HTTP {response.status_code}."

    detail = payload.get("detail", payload.get("message"))
    if isinstance(detail, str) and detail:
        return detail
    if isinstance(detail, list):
        messages = [
            item.get("msg", "")
            for item in detail
            if isinstance(item, dict) and item.get("msg")
        ]
        if messages:
            return " ".join(messages)
    return f"Backend returned HTTP {response.status_code}."


def _headers(token: str | None = None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    **kwargs: Any,
) -> Any:
    response = requests.request(
        method,
        f"{API_BASE_URL}{path}",
        headers={**_headers(token), **kwargs.pop("headers", {})},
        timeout=(10, 60),
        **kwargs,
    )
    if not response.ok:
        if response.status_code == 401:
            raise AuthenticationError(error_message(response))
        raise RuntimeError(error_message(response))
    if response.status_code == 204:
        return None
    if not response.content:
        return None
    return response.json()


def check_health() -> dict[str, Any]:
    return _request("GET", "/api/health")


def login(identifier: str, password: str) -> dict[str, Any]:
    return _request(
        "POST",
        "/api/auth/login",
        json={"identifier": identifier, "password": password},
    )


def register_employee(payload: dict[str, Any]) -> dict[str, Any]:
    return _request("POST", "/api/auth/register", json=payload)


def get_account(token: str) -> dict[str, Any]:
    return _request("GET", "/api/auth/me", token=token)


def logout(token: str) -> None:
    _request("POST", "/api/auth/logout", token=token)


def change_password(token: str, current_password: str, new_password: str) -> dict[str, Any]:
    return _request(
        "POST",
        "/api/auth/change-password",
        token=token,
        json={
            "current_password": current_password,
            "new_password": new_password,
        },
    )


def get_my_employee_record(token: str) -> dict[str, Any]:
    return _request("GET", "/api/employee/me", token=token)


def list_employees(token: str) -> list[dict[str, Any]]:
    return _request("GET", "/api/admin/employees", token=token)


def list_pending_registrations(token: str) -> list[dict[str, Any]]:
    return _request("GET", "/api/admin/registrations", token=token)


def approve_registration(token: str, user_id: int) -> dict[str, Any]:
    return _request(
        "POST", f"/api/admin/registrations/{user_id}/approve", token=token
    )


def reject_registration(token: str, user_id: int) -> None:
    _request("DELETE", f"/api/admin/registrations/{user_id}", token=token)


def create_employee(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request(
        "POST", "/api/admin/employees", token=token, json=payload
    )


def update_employee(
    token: str, user_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    return _request(
        "PATCH",
        f"/api/admin/employees/{user_id}",
        token=token,
        json=payload,
    )


def deactivate_employee(token: str, user_id: int) -> dict[str, Any]:
    return _request("DELETE", f"/api/admin/employees/{user_id}", token=token)


def reactivate_employee(token: str, user_id: int) -> dict[str, Any]:
    return _request(
        "POST", f"/api/admin/employees/{user_id}/reactivate", token=token
    )

def add_attendance_record(
    token: str, user_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    return _request(
        "POST",
        f"/api/admin/employees/{user_id}/attendance",
        token=token,
        json=payload,
    )


def delete_attendance_record(token: str, user_id: int, record_id: int) -> None:
    _request(
        "DELETE",
        f"/api/admin/employees/{user_id}/attendance/{record_id}",
        token=token,
    )


def add_benefit_record(
    token: str, user_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    return _request(
        "POST",
        f"/api/admin/employees/{user_id}/benefits",
        token=token,
        json=payload,
    )


def delete_benefit_record(token: str, user_id: int, record_id: int) -> None:
    _request(
        "DELETE",
        f"/api/admin/employees/{user_id}/benefits/{record_id}",
        token=token,
    )


def stream_chat(question: str, token: str) -> Iterator[dict[str, Any]]:
    with requests.post(
        f"{API_BASE_URL}/api/chat/stream",
        json={"question": question},
        headers={**_headers(token), "Accept": "text/event-stream"},
        stream=True,
        timeout=(10, 300),
    ) as response:
        if not response.ok:
            if response.status_code == 401:
                raise AuthenticationError(error_message(response))
            raise RuntimeError(error_message(response))

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            if not line.startswith("data:"):
                continue
            yield json.loads(line.removeprefix("data:").strip())


def upload_document(uploaded_file: Any, token: str) -> dict[str, Any]:
    response = requests.post(
        f"{API_BASE_URL}/api/ingest",
        headers=_headers(token),
        files={
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                uploaded_file.type or "application/octet-stream",
            )
        },
        timeout=(10, 300),
    )
    if not response.ok:
        if response.status_code == 401:
            raise AuthenticationError(error_message(response))
        raise RuntimeError(error_message(response))
    return response.json()
