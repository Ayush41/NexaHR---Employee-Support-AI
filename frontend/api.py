import json
from collections.abc import Iterator
from typing import Any

import requests

from frontend.config import ADMIN_API_KEY, API_BASE_URL


def error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Backend returned HTTP {response.status_code}."

    detail = payload.get("detail", payload.get("message"))
    if isinstance(detail, str) and detail:
        return detail
    return f"Backend returned HTTP {response.status_code}."


def check_health() -> dict[str, Any]:
    response = requests.get(f"{API_BASE_URL}/api/health", timeout=5)
    response.raise_for_status()
    return response.json()


def stream_chat(question: str) -> Iterator[dict[str, Any]]:
    with requests.post(
        f"{API_BASE_URL}/api/chat/stream",
        json={"question": question},
        headers={"Accept": "text/event-stream"},
        stream=True,
        timeout=(10, 300),
    ) as response:
        if not response.ok:
            raise RuntimeError(error_message(response))

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            if not line.startswith("data:"):
                continue
            payload = json.loads(line.removeprefix("data:").strip())
            yield payload


def upload_document(uploaded_file: Any) -> dict[str, Any]:
    if not ADMIN_API_KEY or ADMIN_API_KEY == "change-me-in-production":
        raise RuntimeError("Set a non-default ADMIN_API_KEY in the project .env file.")

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
        timeout=(10, 300),
    )
    if not response.ok:
        raise RuntimeError(error_message(response))
    return response.json()
