#!/usr/bin/env bash
# One-command setup — run this first on any fresh clone (local or on the ECS server).
set -e

echo "=== Graub AI Setup ==="

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "Installing dependencies..."
pip install -r requirements.txt --quiet --break-system-packages 2>/dev/null || pip install -r requirements.txt --quiet

if [ ! -f ".env" ]; then
    echo "DASHSCOPE_API_KEY=" > .env
    echo ""
    echo "Created .env — add your DASHSCOPE_API_KEY to it before running anything else:"
    echo "  nano .env"
else
    echo ".env already exists — leaving it as is."
fi

echo ""
echo "=== Setup complete. Next steps: ==="
echo "  1. Make sure DASHSCOPE_API_KEY is set in .env"
echo "  2. python test_connection.py     (confirms Qwen Cloud is reachable)"
echo "  3. python seed_demo.py           (populates a realistic demo dataset)"
echo "  4. python web_ui.py              (starts the web portal on :5002)"
