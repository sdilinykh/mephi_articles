#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly update started"
docker compose run --rm updater --all
echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly update finished"
