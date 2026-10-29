from regex import template
from fastapi import FastAPI, Request
from pathlib import Path
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.core.config import get_settings, BASE_DIR
from app.core.logging import configure_logging
from app.services.audit import init_db


# FastAPI App and conneting the API routes, templates and static files

configure_logging()
settings = get_settings()
init_db()

app = FastAPI(title=settings.app_name, version="1.0.0")
app.include_router(router)
app.mount("/static",StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "app_name": settings.app_name})