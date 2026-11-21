from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import BASE_DIR, get_settings
from app.models import Base

settings = get_settings()


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url[len("postgres://") :]
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://") :]
    if database_url.startswith("sqlite:///"):
        sqlite_path = database_url[len("sqlite:///") :]
        if sqlite_path == ":memory:":
            return database_url
        path = Path(sqlite_path)
        if not path.is_absolute():
            path = BASE_DIR / path
        return f"sqlite:///{path.resolve().as_posix()}"
    return database_url


DATABASE_URL = normalize_database_url(settings.database_url)
if DATABASE_URL.startswith("sqlite:///") and ":memory:" not in DATABASE_URL:
    sqlite_path = DATABASE_URL[len("sqlite:///") :]
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

engine_options: dict = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite:"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BASE_DIR / "migrations"))
    config.attributes["connection"] = engine.connect()
    connection = config.attributes["connection"]
    try:
        command.upgrade(config, "head")
    finally:
        connection.close()
