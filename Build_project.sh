#!/usr/bin/env bash


set -e

echo "=========================================================="
echo "         NexaHR - Employee Support AI Copilot             "
echo "=========================================================="

# 1. Resolve script directory to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 2. Check Python installation
echo ""
echo "[1/5] Checking Python installation..."
if command -v python3 &>/dev/null; then
    PY_CMD="python3"
elif command -v python &>/dev/null; then
    PY_CMD="python"
else
    echo "Error: Python was not found in PATH. Please install Python 3.10+."
    exit 1
fi
echo "Using: $($PY_CMD --version)"

# 3. Virtual environment setup
VENV_DIR=".venv"
echo ""
echo "[2/5] Checking virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    $PY_CMD -m venv "$VENV_DIR"
fi

# Activate virtual environment (handles Git Bash / Windows and Linux / macOS)
if [ -f "$VENV_DIR/Scripts/activate" ]; then
    # Windows / Git Bash
    source "$VENV_DIR/Scripts/activate"
elif [ -f "$VENV_DIR/bin/activate" ]; then
    # Linux / macOS / WSL
    source "$VENV_DIR/bin/activate"
else
    echo "Warning: Could not find activate script in $VENV_DIR. Using system python."
fi

# 4. Install dependencies
echo ""
echo "[3/5] Installing/verifying project dependencies..."
python -m pip install --upgrade pip --quiet
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "Warning: requirements.txt not found."
fi

# 5. Ensure required runtime directories and environment files exist
echo ""
echo "[4/5] Setting up directories and configuration..."
mkdir -p data/sample_kb uploads static templates

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
    else
        echo "Warning: .env file not found. Ensure required API keys are configured."
    fi
fi

# Optional knowledge base ingestion flag
if [ "$1" == "--ingest" ] || [ "$1" == "-i" ]; then
    echo ""
    echo "--- Ingesting sample knowledge base ---"
    python ingest_sample_kb.py
fi

# 6. Run the FastAPI Application
echo ""
echo "[5/5] Launching NexaHR application..."
echo "----------------------------------------------------------"
echo " Web UI / Home: http://127.0.0.1:8000"
echo " API Docs     : http://127.0.0.1:8000/docs"
echo " Health check : http://127.0.0.1:8000/api/health"
echo "----------------------------------------------------------"
echo "Press Ctrl+C to terminate."
echo ""

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

