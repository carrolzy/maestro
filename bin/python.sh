#!/usr/bin/env bash
set -euo pipefail

PYTHON="${AI_EFF_PYTHON:-}"

if [ -z "$PYTHON" ]; then
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PYTHON="$candidate"
      break
    fi
  done
fi

if [ -z "$PYTHON" ] || ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Maestro requires Python 3.10+. Set AI_EFF_PYTHON or install Python 3.10+." >&2
  exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  echo "Maestro requires Python 3.10+; $PYTHON is $($PYTHON --version 2>&1)." >&2
  exit 1
fi

exec "$PYTHON" "$@"
