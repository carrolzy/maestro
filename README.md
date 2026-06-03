# Maestro

> An agent orchestration framework — conduct many agents like an orchestra,
> with reusable memory, skills, and task packages as the score.

Maestro is a model-agnostic framework of **reusable AI execution assets** —
layered memory, project-type templates, standing rules, skills, and a
task-package builder — plus an **MCP tool layer** so any LLM-based agent can plug
in and use them.

It externalizes business semantics, conventions, and checklists so an agent does
not need them re-injected on every task. The long-term goal is to grow into an
agent orchestration product that can flexibly serve many business projects; see
[`docs/ROADMAP.md`](docs/ROADMAP.md).

> **Local-first boundary:** this repository contains only the generic framework
> and a worked example project (`projects/example-wxapp/`). Real business
> projects, their memory, and their runtime artifacts are kept local and are
> never committed (see `.gitignore`).

## Concepts

- **Project card** — a project's business context, overrides, and current task
  (`projects/<project>/`), optionally with a `playbook.json` that injects
  domain-specific guidance without any business logic in the core.
- **Layered memory** — project cases (`memory/projects/`) promote to reusable
  patterns (`memory/patterns/`) and then to standing rules (`memory/rules/`).
- **Task package** — a generated, self-contained briefing for a task
  (`tooling/build_task_package.py`), tracked through a run lifecycle
  (`packaged → written_back → synced → closed`).
- **Skills** — packaged procedures under `skills/` for intake, registration,
  memory-first reads, verification, and write-back.

## Default Workflow

1. Identify the project type.
2. Read the project card.
3. Read the project-type template.
4. Read project overrides.
5. Build a task package.
6. Execute the task.
7. Run verification.
8. Write back knowledge.
9. Sync the latest write-back note into local project memory.
10. Search local memory before new work when prior context already exists.

## Quick Start

```bash
git clone <your-repo-url> ai-efficiency-system
cd ai-efficiency-system

# Run the test suite (zero runtime dependencies; Python 3.10+)
PYTHONPATH=tooling python3 -m pytest tooling/tests

# Build a task package against the bundled example project
PYTHONPATH=tooling python3 tooling/build_task_package.py \
  --project example-wxapp \
  --requirement "购物车加购后确认订单金额需要保持一致"

# Search local memory
bin/search-memory.sh --project example-wxapp --query "cart"
```

### Configuration

Paths are configurable via environment variables (with sensible `$HOME` defaults):

- `AI_EFF_VAULT_ROOT` — Obsidian-style write-back vault root
  (default `$HOME/Documents/my-knowledge-base`)
- `AI_EFF_SKILLS_DEST` — local skills install destination override
  (otherwise resolved from the selected `--runtime`; see Local Skill Installation)

## MCP Tool Layer

`tooling/ai_efficiency_mcp_server.py` exposes the core operations as MCP tools so
an agent can call them directly:

`search_memory`, `build_task_package`, `register_project`,
`update_task_run_state`, `writeback_and_sync_memory`, `doctor_local_skills`.

Each tool carries a full `inputSchema` **and** `outputSchema`, the server
negotiates the MCP `protocolVersion` and answers `ping`, and a conformance suite
(`tooling/tests/test_mcp_conformance.py`) checks that every tool's output matches
its declared schema — so any MCP client gets a consistent, discoverable contract.

### Context Pack (any model)

For runtimes without MCP/skills (e.g. raw Gemini/DeepSeek API), emit a
self-contained context pack and inject it into the prompt:

```bash
bin/context-pack.sh --project example-wxapp --requirement "购物车确认订单一致性"
# or write to a file:
bin/context-pack.sh --project example-wxapp --requirement "..." --out pack.md
```

## Directory Map

- `base/` — stable cross-project preferences and rules
- `project-types/` — reusable templates (uniapp mini-program, Chrome extension,
  Node automation, admin dashboard, big-screen dashboard)
- `templates/` — copy-ready file templates
- `projects/` — project cards and overrides (`example-wxapp` ships as a worked
  example; your real projects stay local)
- `checklists/` — implementation checklists for rollout phases
- `memory/` — reusable patterns and standing rules; per-project memory
  accumulates locally as you work
- `skills/` — repo-owned skills (source of truth)
- `bin/` — command wrappers (`register-project.sh`, `search-memory.sh`,
  `bootstrap-skills.sh`, `preflight-public.sh`, …)
- `tooling/` — Python tools, the MCP server, and tests
- `runtime/` — task packages and task-run state (contents kept local)
- `docs/` — [architecture](docs/ARCHITECTURE.md) and [roadmap](docs/ROADMAP.md)

## Local Skill Installation

Repo-local skills live under `skills/` as the source of truth. They are plain
Markdown, so they work across agent runtimes — only the install directory
differs. Pick your runtime with `--runtime` (`codex`, `claude`, or `generic`):

```bash
bin/doctor-local-skills.sh   --runtime claude
bin/bootstrap-skills.sh      --runtime claude
bin/install-local-skills.sh  --runtime claude --all
```

Resolution order for the install destination: `--dest` → `AI_EFF_SKILLS_DEST`
→ the runtime's default (e.g. `~/.codex/skills`, `~/.claude/skills`). The
installer only overwrites skill directories previously installed by this
repo-owned installer, so it will not silently replace unrelated local skills.
Restart the agent runtime after installing so trigger metadata reloads.

For MCP-capable clients you don't need to install skills at all — point the
client at `tooling/ai_efficiency_mcp_server.py` (see
[ARCHITECTURE.md](docs/ARCHITECTURE.md#integrations--model-adapters)).

## License

[MIT](LICENSE)
