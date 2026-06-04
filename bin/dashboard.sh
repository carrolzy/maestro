#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${AI_EFF_PYTHON:-python3}"
PORT="${PORT:-8420}"

echo "🖥   Maestro Dashboard → http://localhost:${PORT}"
echo "   Press Ctrl+C to stop."
echo ""

PYTHONPATH="$ROOT_DIR/tooling${PYTHONPATH:+:$PYTHONPATH}" \
  exec "$PYTHON" "$ROOT_DIR/tooling/api_server.py" --port "$PORT" --system-root "$ROOT_DIR" --open
