#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/macbook/Desktop/Masters_degree/mephi-journals-dashboard"
LOG_DIR="$PROJECT_DIR/logs"
PYTHON="$PROJECT_DIR/.venv/bin/python"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://mephi:mephi@localhost:5432/mephi_journals}"
export PYTHONPATH="$PROJECT_DIR"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly update started"
docker compose up -d postgres
"$PYTHON" -m src.pipeline.update --all
echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly update finished"
