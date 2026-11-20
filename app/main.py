
from html import escape

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import get_settings, BASE_DIR
from app.core.logging import configure_logging
from app.services.audit import init_db
from app.services.accounts import initialize_account_store


# Configure logging and application settings
configure_logging()
settings = get_settings()


# Ensure required directories exist
(BASE_DIR / "static").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "templates").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "uploads").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)


# Initialize FastAPI application
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
)

# Register API routes
app.include_router(router)


@app.on_event("startup")
def initialize_application() -> None:
    init_db()
    initialize_account_store()

# Mount static files
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

@app.get("/", response_class=HTMLResponse)
def home():
    frontend_url = escape(settings.streamlit_app_url, quote=True)
    app_name = escape(settings.app_name)
    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{app_name} API</title>
        <style>
          body {{ background: #f5f7fb; color: #17233c; font: 16px system-ui, sans-serif;
                 margin: 0; min-height: 100vh; display: grid; place-items: center; }}
          main {{ background: white; border: 1px solid #e8edf5; border-radius: 20px;
                  box-shadow: 0 16px 48px #17233c12; max-width: 560px; padding: 40px; }}
          h1 {{ margin: 0 0 12px; }} p {{ color: #65728a; line-height: 1.6; }}
          a {{ color: #3455d1; font-weight: 650; }}
          .links {{ display: flex; gap: 24px; margin-top: 24px; }}
        </style>
      </head>
      <body><main>
        <h1>{app_name} backend is running</h1>
        <p>The employee and administrator workspace is served by the Streamlit frontend.
           The FastAPI service provides authenticated APIs for chat and employee records.</p>
        <div class="links">
          <a href="{frontend_url}">Open NexaHR workspace</a>
          <a href="/docs">API documentation</a>
        </div>
      </main></body>
    </html>
    """
