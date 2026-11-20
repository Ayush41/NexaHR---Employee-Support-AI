FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=10000

WORKDIR /app

COPY requirements-backend.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-backend.txt

COPY app ./app
COPY alembic.ini .
COPY migrations ./migrations
COPY templates ./templates
COPY static ./static
COPY data/sample_kb ./data/sample_kb

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app app \
    && mkdir -p /app/uploads /app/data \
    && chown -R app:app /app

USER app

EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
