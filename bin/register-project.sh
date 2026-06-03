#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$ROOT_DIR/tooling${PYTHONPATH:+:$PYTHONPATH}" \
  python3 "$ROOT_DIR/tooling/register_project.py" "$@"
