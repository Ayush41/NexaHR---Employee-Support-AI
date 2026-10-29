# Centralized Setting class

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "NexaHR"
    app_env: str = "development"

    # LLM Settings (Groq & OpenAI fallback)
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Search & Vector DB
    tavily_api_key: str = ""
    pinecone_api_key: str = ""
    pinecone_index_name: str = "NexaHR_Policy-RAG"
    pinecone_namespace: str = "company-hr-kb"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    top_k: int = 4
    max_retries: int = 1
    admin_api_key: str = "change-me-in-production"
    audit_db_path: str = str(BASE_DIR / "data" / "audit.db")
    upload_dir: str = str(BASE_DIR / "uploads")
    sample_kb_dir: str = str(BASE_DIR / "data" / "sample_kb")

    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()