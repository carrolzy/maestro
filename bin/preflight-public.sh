#!/usr/bin/env bash
# Preflight check before publishing / committing to a public repo.
# Scans BOTH tracked file contents AND tracked file NAMES for private
# business identifiers, using a broad case-insensitive pattern (so variants
# like "GCC WXApp" are caught, not only "gcc-wxapp").
#
# Exit 0 + "CLEAN" when nothing is found; non-zero + the offending paths
# otherwise. Run from the repo root.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Private identifiers that must never reach a public repo. Extend as needed.
PATTERN='gcc.?wxapp|wwj.?wxapp|hyx|capture.?goods|landslide|mryitao|oknjc1|/Users/oknjc1|1688'

# This script intentionally contains the pattern above, so exclude it (and any
# other known false-positive carriers) from the scan.
SELF='bin/preflight-public.sh'

scanned="$(git ls-files | grep -vxF "$SELF" || true)"
content_hits="$(printf '%s\n' "$scanned" | xargs grep -lIiE "$PATTERN" 2>/dev/null || true)"
name_hits="$(printf '%s\n' "$scanned" | grep -iE "$PATTERN" || true)"

if [ -n "$content_hits" ] || [ -n "$name_hits" ]; then
  echo "❌ NOT CLEAN — private identifiers found:"
  if [ -n "$content_hits" ]; then
    echo "--- in file contents ---"
    echo "$content_hits"
  fi
  if [ -n "$name_hits" ]; then
    echo "--- in file names ---"
    echo "$name_hits"
  fi
  exit 1
fi

echo "✅ CLEAN — no private identifiers in tracked contents or names"
exit 0
