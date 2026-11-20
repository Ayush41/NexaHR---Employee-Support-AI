import os
from pathlib import Path

import streamlit as st
from dotenv import dotenv_values
from streamlit.errors import StreamlitSecretNotFoundError

ROOT_DIR = Path(__file__).resolve().parents[1]
LOCAL_SETTINGS = dotenv_values(ROOT_DIR / ".env")


def _get_setting(name: str, default: str = "") -> str:
    environment_value = os.getenv(name)
    if environment_value:
        return environment_value

    try:
        secret_value = st.secrets.get(name)
    except StreamlitSecretNotFoundError:
        secret_value = None
    if secret_value is not None:
        return str(secret_value)
    local_value = LOCAL_SETTINGS.get(name)
    return str(local_value) if local_value is not None else default


API_BASE_URL = _get_setting(
    "API_BASE_URL", "http://127.0.0.1:8888"
).rstrip("/")
APP_ENV = _get_setting("APP_ENV", "development").strip().casefold()
