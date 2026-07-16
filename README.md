# ⚡ Maestro — Model-Agnostic Agent Orchestration

Maestro is an **agent orchestration product** that any LLM can plug into — Claude,
Codex, Gemini, DeepSeek, or any MCP-capable client. It gives every connected model
the same reusable infrastructure: project onboarding, memory search, task packaging,
tool execution, and deterministic multi-step workflows.

Started as a personal AI efficiency system, Maestro has evolved into a complete
**local Agent OS** — from CLI toolbox to visual dashboard. No cloud required.
Everything runs on your machine.

> 🇨🇳 [中文文档](README.zh-CN.md)

---

## What It Does

| Capability | What it gives you |
|---|---|
| **Project onboarding** | Register any project with one command (or a web form). Auto-generates business context, playbook, and a machine-readable business card. |
| **Memory system** | Layered memory (project cards, cases, patterns, rules) that the model reads before work and writes back after. |
| **Task packaging** | Build a self-contained task brief from project context + requirement text — injectable into any model prompt. |
| **MCP tool layer** | 16 MCP tools with full `inputSchema` / `outputSchema` and a conformance suite. Any MCP client gets discoverable, validated contracts. |
| **Provider adapters** | Same 16 tools in OpenAI, DeepSeek, Anthropic, and Gemini native function-calling formats. Thin translators, zero business logic. |
| **Workflow engine** | Deterministic DAG executor — define steps with dependencies, the engine runs them in parallel with lifecycle state tracking, verification gates, and retries. |
| **Visual dashboard** | Single-page web UI — browse projects, invoke tools, run workflows, search memory. All clickable, zero CLI memorization. |

---

## Quick Start

### Prerequisites

- **Python 3.10+** (the code uses `X | None` syntax)
- A terminal

### Install

```bash
git clone https://github.com/carrolzy/maestro.git
cd maestro

# One command to set up everything for Claude Code (or any MCP client):
bin/setup-claude.sh
```

The setup script auto-detects your Python, installs all 12 Maestro skills,
creates `.mcp.json` for MCP tool access, and runs a health check. **You're
done.** Restart Claude Code and you can immediately say "list my projects" or
"onboard a new project."

No `pip install`. No `npm install`. No manual config. Maestro is pure Python
stdlib + vanilla HTML/CSS/JS.

> 💡 **Using Codex or Cursor instead?** The same setup works — just run
> `bin/setup-claude.sh` (it installs skills to `~/.claude/skills/`). For
> Codex specifically, also run: `bin/bootstrap-skills.sh --runtime codex`

### Your first project

**Web dashboard (recommended for beginners):**

```bash
bin/dashboard.sh
# → opens http://localhost:8420
# → click "+ New", fill in the form, click "Create"
```

**Ask Claude to do it for you:**

> "Onboard a new project called my-app — it's an e-commerce mini-program"

Claude calls `register_project` via MCP, generates the playbook, validates
everything. 30 seconds.

**Interactive CLI:**

```bash
bin/onboard-project.sh
# → answers three prompts (slug, summary, type)
# → ✅ All checks passed
```
bin/dashboard.sh
# → opens http://localhost:8420
# → click "+ New", fill in the form, click "Create"
```

**Interactive CLI:**

```bash
bin/onboard-project.sh
# → answers three prompts (slug, summary, type)
# → ✅ All checks passed
```

**For scripts / CI:**

```bash
bin/onboard-project.sh \
  --project my-app \
  --summary "An e-commerce mini-program" \
  --project-type uniapp-mini-program
```

### Build a task package

```bash
bin/context-pack.sh --project my-app --requirement "Add a shopping cart confirmation page"
# prints package.md to stdout — inject into any LLM prompt
```

### Run a workflow

```bash
# Via the dashboard: Workflows tab → pick a preset → click Run
# Via the API:
curl -X POST http://localhost:8420/api/workflows/run \
  -H 'Content-Type: application/json' \
  -d '{"project":"my-app","steps":[
    {"id":"s1","tool":"search_memory","args":{"query":"cart"}},
    {"id":"s2","tool":"validate_project","args":{"project":"my-app"}}
  ]}'
```

### Use with Claude Code / Cursor (MCP)

Add to your MCP client config:

```json
{
  "mcpServers": {
    "maestro": {
      "command": "python3",
      "args": ["tooling/ai_efficiency_mcp_server.py"],
      "env": {
        "PYTHONPATH": "<path-to-maestro>/tooling"
      }
    }
  }
}
```

### Use with OpenAI / DeepSeek / Gemini (raw API)

```bash
# Get provider-native tool declarations (copy into your API call)
bin/provider-tools.sh --provider openai --list
bin/provider-tools.sh --provider gemini --list
bin/provider-tools.sh --provider anthropic --list
```

---

## Architecture

Maestro is built in five phases. Each phase adds a layer without breaking the
previous ones.

```
┌─────────────────────────────────────────────────────┐
│  Phase 5 — Visual Dashboard                         │
│  bin/dashboard.sh → api_server.py → dashboard.html  │
├─────────────────────────────────────────────────────┤
│  Phase 4 — Orchestration Runtime                    │
│  workflow_engine.py (DAG + parallel + retry)        │
│  workflow_state.py (lifecycle state machine)        │
├─────────────────────────────────────────────────────┤
│  Phase 3 — Pluggable Business Onboarding            │
│  playbook_schema.py • business_card.py              │
│  validate_project.py • onboard_project.py           │
├─────────────────────────────────────────────────────┤
│  Phase 2 — Model-Agnostic Adapters                  │
│  adapters/ (OpenAI • DeepSeek • Anthropic • Gemini) │
│  tool_registry.py (canonical specs)                 │
├─────────────────────────────────────────────────────┤
│  Phase 1 — MCP Tool Layer                           │
│  ai_efficiency_mcp_server.py (16 tools, schemas)    │
│  context_pack.py (raw-API context injection)        │
├─────────────────────────────────────────────────────┤
│  Phase 0 — Reusable Asset Library                   │
│  memory/ • projects/ • project-types/ • templates/  │
│  skills/ • tooling/*.py                             │
└─────────────────────────────────────────────────────┘
```

**Design principles:**
- **Business stays out of core.** Generic engine + per-project config (`playbook.json`, `business-card.json`) only.
- **Memory before work.** Read prior context before starting; write back after.
- **Verify before close.** No task closed without evidence.
- **Zero runtime dependencies.** Tooling uses Python stdlib only. Dashboard uses vanilla JS/CSS — no build step, no npm.
- **Model-agnostic.** No LLM calls in core code. Every surface (MCP, adapters, dashboard API) dispatches through the same canonical `server.invoke()`.

---

## Project Structure

```
maestro/
├── bin/                          # One-command launchers
│   ├── dashboard.sh              #   Start visual dashboard
│   ├── onboard-project.sh        #   Interactive project onboarding
│   ├── context-pack.sh           #   Emit model-agnostic task context
│   └── provider-tools.sh         #   Provider-native tool declarations
│
├── tooling/                      # Core engine (pure Python, zero deps)
│   ├── ai_efficiency_mcp_server.py  # MCP JSON-RPC server (16 tools)
│   ├── tool_registry.py          #   Canonical tool specs (single source of truth)
│   ├── adapters/                 #   Per-provider format translators
│   │   ├── openai.py / anthropic.py / gemini.py / base.py
│   ├── workflow_engine.py        #   Deterministic DAG executor
│   ├── workflow_state.py         #   Lifecycle state machine
│   ├── onboard_project.py        #   Guided onboarding (CLI + API)
│   ├── validate_project.py       #   Project readiness validator
│   ├── playbook_schema.py        #   playbook.json schema + validator
│   ├── business_card.py          #   business-card.json schema + helpers
│   ├── project_types.py          #   Project-type discovery
│   ├── api_server.py             #   Dashboard REST API (stdlib http.server)
│   ├── context_pack.py           #   Model-agnostic context pack emitter
│   ├── jsonschema_mini.py        #   Zero-dep JSON Schema validator
│   ├── task_package_builder.py   #   Build task packages from context
│   ├── search_memory.py          #   Search layered memory
│   ├── register_project.py       #   Register new project shells
│   ├── update_task_run_state.py  #   Task lifecycle state persistence
│   ├── writeback_and_sync_memory.py  # Obsidian write-back + memory sync
│   ├── local_skills_doctor.py    #   Skills installation diagnostics
│   ├── runtime_targets.py        #   Agent runtime registry
│   ├── ui/
│   │   └── dashboard.html        #   Single-page visual dashboard
│   └── tests/                    #   147 tests (unittest, zero deps)
│
├── projects/                     # Per-project config (business data — local only)
│   └── example-wxapp/            #   Sample project for demonstration
│       ├── business-context.md   #   Human-readable project description
│       ├── playbook.json         #   Domain-specific guidance
│       └── ...
│
├── project-types/                # Reusable project-type templates
│   ├── uniapp-mini-program/      #   Mini-program / uniapp
│   ├── admin-dashboard/          #   Back-office systems
│   ├── big-screen-dashboard/     #   Large-screen / visualization
│   ├── chrome-extension/         #   Browser extensions
│   └── node-automation/          #   Scripts / automation
│
├── memory/                       # Layered persistent memory
│   ├── patterns/                 #   Reusable solution patterns
│   ├── rules/                    #   Standing rules
│   └── projects/                 #   Per-project cases
│
├── templates/                    # Canonical markdown templates
├── skills/                       # Markdown skills (install per-runtime)
├── docs/                         # Documentation
│   ├── ARCHITECTURE.md
│   └── ROADMAP.md
│
├── README.md                     # You are here
└── README.zh-CN.md               # 中文文档
```

---

## Tools Reference

These 16 tools are available via MCP, provider adapters, dashboard, and API:

| Tool | Description |
|---|---|
| `search_memory` | Search project cards, cases, patterns, and rules |
| `build_task_package` | Build a task brief from project context + requirement |
| `register_project` | Create a new project shell from templates |
| `update_task_run_state` | Record task lifecycle state transitions |
| `writeback_and_sync_memory` | Write a note into vault + sync to memory |
| `doctor_local_skills` | Diagnose local skill installation status |
| `validate_project` | Check project readiness (files, playbook, card, type) |
| `list_project_types` | List available project-type templates with metadata |
| `run_workflow` | Execute a DAG workflow definition |
| `get_workflow_status` | Query workflow run status by project + task_slug |
| `resume_task` | Build full resume context from checkpoints (A2A) |
| `handoff_task` | Explicit agent-to-agent handoff with checkpoint |
| `set_active_task` | Point edit-checkpointing at the current task; provisions its scratch dir |
| `snapshot_task` | Git-based checkpoint of changed files (runtime-independent) |
| `gc_artifacts` | Artifact lifecycle: scan / archive (gzip, reversible) / clean (TTL, dry-run) / restore |
| `register_temp_file` | Register an in-repo helper file with a TTL so GC reclaims it later |

---

## Workflow Engine

Define steps with dependencies — the engine handles the rest:

```json
{
  "project": "my-app",
  "task_slug": "2026-06-04-cart-consistency",
  "steps": [
    { "id": "plan",    "tool": "build_task_package", "args": {...} },
    { "id": "impl-a",  "tool": "...", "args": {...}, "depends_on": ["plan"] },
    { "id": "impl-b",  "tool": "...", "args": {...}, "depends_on": ["plan"] },
    { "id": "verify",  "tool": "...", "args": {...}, "depends_on": ["impl-a", "impl-b"], "verify": {"condition": "no_error"} },
    { "id": "close",   "tool": "writeback_and_sync_memory", "args": {...}, "depends_on": ["verify"] }
  ]
}
```

- Steps with **no inter-dependencies** run in **parallel**
- **`verify`** gate blocks progression on failure
- **`retry`** with `max_attempts` on any step
- Built-in **`fan_out`** verb for parallel tool arrays
- Full lifecycle state machine: `pending → in_progress → verifying → completed | failed → retry`

---

## Running Tests

```bash
PYTHONPATH=tooling python3 -m unittest discover -s tooling/tests -p 'test_*.py'
# 249 tests pass — requires Python 3.10+ (the default `python3` must be 3.10+,
# not macOS's bundled 3.9; `zip(strict=True)` / PEP 604 fail on 3.9)
```

---

## Development

- **Branch model:** `main` = clean/releasable, `develop` = work
- **Commit style:** Conventional Commits
- **Preflight:** `bash bin/preflight-public.sh` — blocks business data from reaching the public repo
- **Python target:** 3.10+ (PEP 604 `X | None` syntax)
- **Dependency policy:** Zero runtime dependencies for tooling. Dashboard is vanilla HTML/CSS/JS.

---

## License

MIT — see [LICENSE](LICENSE).

---

🤖 Built with [Claude Code](https://claude.com/claude-code)
