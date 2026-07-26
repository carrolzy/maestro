#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$ROOT_DIR/tooling${PYTHONPATH:+:$PYTHONPATH}" \
  exec "$ROOT_DIR/bin/python.sh" "$ROOT_DIR/tooling/install_local_skills.py" "$@"
