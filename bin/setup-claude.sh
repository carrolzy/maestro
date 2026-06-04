#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════════
# Maestro — one-command Claude Code setup
# ═══════════════════════════════════════════════════════════════════
#
# Run this once after cloning Maestro. It:
#   1. Finds a Python 3.10+
#   2. Installs all 12 Maestro skills into ~/.claude/skills/
#   3. Creates .mcp.json so Claude can call Maestro's 14 tools
#   4. Runs a quick health check
#
# After this, restart Claude Code (or start a new session) and you're
# ready to use Maestro — no manual config needed.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo ""
echo "⚡ Maestro — Claude Code Setup"
echo "════════════════════════════════"
echo ""

# ── 1. Find a working Python 3.10+ ─────────────────────────────────

PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" &>/dev/null; then
    version=$("$candidate" -c "import sys; print(sys.version_info[:2])" 2>/dev/null || echo "(0,0)")
    major=$(echo "$version" | grep -o '[0-9]\+' | head -1)
    minor=$(echo "$version" | grep -o '[0-9]\+' | tail -1)
    if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
      PYTHON="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo "❌  No Python 3.10+ found. Please install Python 3.10 or later."
  echo "   brew install python@3.13"
  exit 1
fi

echo "✅  Python: $PYTHON ($("$PYTHON" --version))"

# ── 2. Install skills ─────────────────────────────────────────────

echo ""
echo "📦  Installing Maestro skills for Claude Code..."
echo ""

PYTHONPATH="$ROOT_DIR/tooling" "$PYTHON" "$ROOT_DIR/tooling/install_local_skills.py" --all --runtime claude

echo ""
echo "✅  Skills installed"

# ── 3. Create .mcp.json ───────────────────────────────────────────

MCP_FILE="$ROOT_DIR/.mcp.json"

if [ -f "$MCP_FILE" ]; then
  echo ""
  echo "⏭   .mcp.json already exists — skipping."
else
  cat > "$MCP_FILE" <<MCPEOF
{
  "mcpServers": {
    "maestro": {
      "command": "$PYTHON",
      "args": ["tooling/ai_efficiency_mcp_server.py"],
      "env": {
        "PYTHONPATH": "\${MCP_PROJECT_DIR}/tooling"
      }
    }
  }
}
MCPEOF
  echo ""
  echo "✅  .mcp.json created (using $PYTHON)"
fi

# ── 4. Health check ───────────────────────────────────────────────

echo ""
echo "🩺  Running health check..."
echo ""

set +e
HEALTH_OUTPUT=$(PYTHONPATH="$ROOT_DIR/tooling" "$PYTHON" -c "
from ai_efficiency_mcp_server import AiEfficiencyMcpServer
from pathlib import Path
server = AiEfficiencyMcpServer(system_root=Path('$ROOT_DIR'))
tools = len(server._tools)
print(f'Tools: {tools}')
# test one tool
result = server.invoke('list_project_types', {})
types = len(result.get('project_types', []))
print(f'Project types: {types}')
print('OK')
" 2>&1)
EXIT_CODE=$?
set -e

echo "$HEALTH_OUTPUT"

if [ "$EXIT_CODE" -eq 0 ] && echo "$HEALTH_OUTPUT" | grep -q "OK"; then
  echo ""
  echo "✅  Health check passed"
else
  echo ""
  echo "⚠️   Health check had issues. Tools may not work until Claude restarts."
fi

# ── 5. Done ───────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════"
echo "🎉  Maestro is ready for Claude!"
echo ""
echo "   Next steps:"
echo "   1. Restart Claude Code (or open a new session)"
echo "   2. Say: 'list my Maestro projects' or 'onboard a new project'"
echo "   3. Start the dashboard: bin/dashboard.sh"
echo ""
echo "   Skills installed: ~/.claude/skills/"
echo "   MCP config:       .mcp.json"
echo "   Dashboard:        bin/dashboard.sh"
echo ""
