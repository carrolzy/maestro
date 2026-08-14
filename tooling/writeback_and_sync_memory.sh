#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_ROOT="${VAULT_ROOT:-${AI_EFF_VAULT_ROOT:-$HOME/Documents/my-knowledge-base}}"

if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <project-slug> <note-path> <source-file> [--append]"
  exit 1
fi

PROJECT="$1"
NOTE_PATH="$2"
SOURCE_FILE="$3"
shift 3

python3 "$SCRIPT_DIR/writeback_and_sync_memory.py" \
  --vault-root "$VAULT_ROOT" \
  --project "$PROJECT" \
  --note-path "$NOTE_PATH" \
  --source-file "$SOURCE_FILE" \
  "$@"
