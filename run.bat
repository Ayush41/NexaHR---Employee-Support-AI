@echo off
setlocal enabledelayedexpansion

echo ==========================================================
echo          NexaHR - Employee Support AI Copilot             
echo ==========================================================

cd /d "%~dp0"

if not exist ".venv" (
    echo [1/4] Creating virtual environment (.venv)...
    python -m venv .venv
) else (
    echo [1/4] Virtual environment found (.venv).
)

call .venv\Scripts\activate.bat

echo [2/4] Verifying dependencies...
python -m pip install -r requirements.txt

echo [3/4] Ensuring directories exist...
if not exist "data\sample_kb" mkdir data\sample_kb
if not exist "uploads" mkdir uploads
if not exist "static" mkdir static
if not exist "templates" mkdir templates

if "%1"=="--ingest" (
    echo Ingesting sample knowledge base...
    python ingest_sample_kb.py
)

echo [4/4] Starting server...
echo ----------------------------------------------------------
echo  Web UI / Home: http://127.0.0.1:8888
echo  API Docs     : http://127.0.0.1:8888/docs
echo  Health check : http://127.0.0.1:8888/api/health
echo ----------------------------------------------------------
uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
pause

