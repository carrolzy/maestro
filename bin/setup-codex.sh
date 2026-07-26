#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════════
# Maestro — one-command Codex setup
# ═══════════════════════════════════════════════════════════════════
#
# Run this once per machine. It:
#   1. Finds a Python 3.10+
#   2. Installs all Maestro skills into ~/.codex/skills/
#   3. Adds Maestro MCP server to ~/.codex/config.toml
#   4. Trusts the Maestro project directory
#   5. Runs a quick health check
#
# After this, restart Codex and you're ready.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo ""
echo "⚡ Maestro — Codex Setup"
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
echo "📦  Installing Maestro skills for Codex..."
echo ""

PYTHONPATH="$ROOT_DIR/tooling" "$PYTHON" "$ROOT_DIR/tooling/install_local_skills.py" --all --runtime codex

echo ""
echo "✅  Skills installed"

# ── 3. Add MCP server to Codex config ──────────────────────────────

CODEX_CONFIG="$HOME/.codex/config.toml"
MCP_SECTION="[mcp_servers.maestro]"

if [ -f "$CODEX_CONFIG" ] && grep -qF "$MCP_SECTION" "$CODEX_CONFIG"; then
  echo ""
  echo "⏭   Maestro MCP server already in Codex config — skipping."
else
  echo ""
  echo "🔧  Adding Maestro MCP server to Codex config..."

  # Ensure config exists
  touch "$CODEX_CONFIG"

  # Append the MCP server section
  cat >> "$CODEX_CONFIG" <<MCPEOF

# ── Maestro (added by bin/setup-codex.sh) ──
[mcp_servers.maestro]
command = "$PYTHON"
args = ["$ROOT_DIR/tooling/ai_efficiency_mcp_server.py"]
startup_timeout_sec = 30.0

[mcp_servers.maestro.env]
PYTHONPATH = "$ROOT_DIR/tooling"

# Auto-approve all 21 Maestro tools (they are local and safe)
[mcp_servers.maestro.tools.search_memory]
approval_mode = "approve"

[mcp_servers.maestro.tools.build_task_package]
approval_mode = "approve"

[mcp_servers.maestro.tools.register_project]
approval_mode = "approve"

[mcp_servers.maestro.tools.update_task_run_state]
approval_mode = "approve"

[mcp_servers.maestro.tools.writeback_and_sync_memory]
approval_mode = "approve"

[mcp_servers.maestro.tools.doctor_local_skills]
approval_mode = "approve"

[mcp_servers.maestro.tools.validate_project]
approval_mode = "approve"

[mcp_servers.maestro.tools.list_project_types]
approval_mode = "approve"

[mcp_servers.maestro.tools.run_workflow]
approval_mode = "approve"

[mcp_servers.maestro.tools.get_workflow_status]
approval_mode = "approve"

[mcp_servers.maestro.tools.resume_task]
approval_mode = "approve"

[mcp_servers.maestro.tools.handoff_task]
approval_mode = "approve"

[mcp_servers.maestro.tools.set_active_task]
approval_mode = "approve"

[mcp_servers.maestro.tools.snapshot_task]
approval_mode = "approve"

[mcp_servers.maestro.tools.gc_artifacts]
approval_mode = "approve"

[mcp_servers.maestro.tools.register_temp_file]
approval_mode = "approve"

[mcp_servers.maestro.tools.grep_code]
approval_mode = "approve"

[mcp_servers.maestro.tools.glob_files]
approval_mode = "approve"

[mcp_servers.maestro.tools.read_file_slice]
approval_mode = "approve"

[mcp_servers.maestro.tools.repo_outline]
approval_mode = "approve"

[mcp_servers.maestro.tools.audit_tests]
approval_mode = "approve"
MCPEOF

  echo "✅  Maestro MCP server added to $CODEX_CONFIG"
fi

ensure_tool_approval() {
  local tool_name="$1"
  local section="[mcp_servers.maestro.tools.$tool_name]"

  if grep -qF "$section" "$CODEX_CONFIG"; then
    return
  fi

  cat >> "$CODEX_CONFIG" <<TOOLEOF

$section
approval_mode = "approve"
TOOLEOF
}

# Existing Maestro configurations need approval entries added as tools evolve.
for tool_name in \
  search_memory build_task_package register_project update_task_run_state \
  writeback_and_sync_memory doctor_local_skills validate_project list_project_types \
  run_workflow get_workflow_status resume_task handoff_task set_active_task \
  snapshot_task gc_artifacts register_temp_file grep_code glob_files \
  read_file_slice repo_outline audit_tests; do
  ensure_tool_approval "$tool_name"
done

# ── 3.5 Register the forced-checkpoint PostToolUse hook ────────────

if [ -f "$CODEX_CONFIG" ] && grep -qF "checkpoint_hook.py" "$CODEX_CONFIG"; then
  echo ""
  echo "⏭   Checkpoint hook already registered — skipping."
else
  echo ""
  echo "🪝  Registering checkpoint hook in Codex config..."
  cat >> "$CODEX_CONFIG" <<HOOKEOF

# ── Maestro checkpoint hook (added by bin/setup-codex.sh) ──
# Auto-records every file edit to a checkpoint so a crashed/interrupted
# Codex session can be resumed by Claude (or vice versa).
# NOTE: Codex (as of 0.135) only fires PostToolUse reliably for the shell/Bash
# tool — apply_patch / MCP edits don't fire yet (openai/codex#16732). So we
# match shell here; the hook parses the command text for the written file
# (apply_patch heredoc, > redirection, tee, sed -i) and records nothing for
# non-write commands. Edit|Write|apply_patch stay listed for forward-compat.
[[hooks.PostToolUse]]
matcher = "shell|Bash|apply_patch|Edit|Write"

[[hooks.PostToolUse.hooks]]
type = "command"
command = '$PYTHON "$ROOT_DIR/tooling/hooks/checkpoint_hook.py"'
timeout = 10
statusMessage = "Recording checkpoint"
HOOKEOF
  echo "✅  Checkpoint hook registered (fires after every file edit, records it)"
  echo "    ⚠️  Codex requires you to TRUST new hooks: run /hooks in Codex once,"
  echo "        review the Maestro checkpoint hook, and trust it."
fi

# ── 4. Trust the Maestro project directory ─────────────────────────

if [ -f "$CODEX_CONFIG" ] && grep -qF "[projects.\"$ROOT_DIR\"]" "$CODEX_CONFIG"; then
  echo ""
  echo "⏭   Project already trusted — skipping."
else
  cat >> "$CODEX_CONFIG" <<TRUSTEOF

[projects."$ROOT_DIR"]
trust_level = "trusted"
TRUSTEOF
  echo ""
  echo "✅  Project trusted: $ROOT_DIR"
fi

# ── 5. Health check ───────────────────────────────────────────────

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
  echo "⚠️   Health check had issues. Tools may not work until Codex restarts."
fi

# ── 6. Done ───────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════"
echo "🎉  Maestro is ready for Codex!"
echo ""
echo "   Next steps:"
echo "   1. Restart Codex (or open a new session)"
echo "   2. Run /hooks in Codex and trust the Maestro checkpoint hook"
echo "   3. Codex now has 21 Maestro MCP tools (auto-approved)"
echo "   4. Say: 'list my projects' or 'onboard a new project'"
echo "   5. Start the dashboard: bin/dashboard.sh"
echo ""
echo "   Skills:   ~/.codex/skills/"
echo "   MCP:      ~/.codex/config.toml  [mcp_servers.maestro]"
echo "   Project:  $ROOT_DIR (trusted)"
echo ""
