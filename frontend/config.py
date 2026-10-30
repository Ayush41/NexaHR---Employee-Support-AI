import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8888").rstrip("/")
ADMIN_USERNAME = os.getenv("NEXAHR_ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("NEXAHR_ADMIN_PASSWORD", "")
EMPLOYEE_USERNAME = os.getenv("NEXAHR_EMPLOYEE_USERNAME", "")
EMPLOYEE_PASSWORD = os.getenv("NEXAHR_EMPLOYEE_PASSWORD", "")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
