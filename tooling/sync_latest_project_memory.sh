#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_ROOT="${VAULT_ROOT:-${AI_EFF_VAULT_ROOT:-$HOME/Documents/my-knowledge-base}}"

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <project-slug> [count]"
  exit 1
fi

PROJECT="$1"
COUNT="${2:-1}"

python3 "$SCRIPT_DIR/sync_project_notes_to_memory.py" \
  --vault-root "$VAULT_ROOT" \
  --project "$PROJECT" \
  --count "$COUNT"
