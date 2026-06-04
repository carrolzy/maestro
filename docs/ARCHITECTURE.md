# Maestro Architecture

Maestro turns repeated, cross-project engineering context into durable,
reusable execution assets, and exposes them so any LLM-based agent can plug in.
This document describes the layers, the end-to-end flow, the extension points,
and how different model runtimes integrate.

## Design Principles

- **Business stays out of core.** The engine is generic; anything
  project-specific lives in per-project config (`projects/<project>/`,
  including an optional `playbook.json`), never in engine code.
- **Memory before work, verify before close.** Read prior context before
  starting; record evidence before a task is considered done.
- **Local-first.** Real project data accumulates locally and is never published.
- **Thin orchestration, logic in code.** Skills decide *when* a process applies
  and call backend tooling; the Python layer owns the actual logic.

## Layers

| Layer | Location | Role |
|-------|----------|------|
| Global rules / preferences | `base/` | Stable cross-project operating profile |
| Project-type templates | `project-types/` | Reusable defaults per class of project |
| File templates | `templates/` | Copy-ready scaffolding for project cards |
| Project cards | `projects/<project>/` | Business context, overrides, current task, optional `playbook.json` |
| Memory | `memory/` | Project cases → reusable patterns → standing rules |
| Skills | `skills/` | Process orchestration (intake, register, memory-first, verify, write-back) |
| Tooling | `tooling/` + `bin/` | Executable backend + the MCP server |
| Runtime artifacts | `runtime/` | Generated task packages and task-run state (local) |

## End-to-End Flow

1. Register the project (`tooling/register_project.py`).
2. Build a task package for a requirement (`tooling/build_task_package.py`).
3. Read minimum pre-work memory (project card, recent cases, patterns, rules).
4. Execute the work.
5. Verify, then record task-run state (`packaged → written_back → synced → closed`).
6. Write back a durable note and sync it into project memory.
7. Search memory before later related work.

## The `playbook.json` Extension Point

A project can drop a `projects/<project>/playbook.json` to inject
domain-specific guidance (suspected modules, risk flags, verification checks)
keyed by requirement keywords — **without any business logic in the engine**.
The builder (`tooling/task_package_builder.py`) loads it when present and stays
fully generic when absent. See `projects/example-wxapp/playbook.json` for a
worked example.

## Integrations / Model Adapters

The core engine is pure Python with **no model calls** — it is model-agnostic
by construction. Integration happens at the edges:

- **MCP clients (Claude, Cursor, any MCP-capable agent):** run the MCP server
  (`tooling/ai_efficiency_mcp_server.py`). It exposes `search_memory`,
  `build_task_package`, `register_project`, `update_task_run_state`,
  `writeback_and_sync_memory`, and `doctor_local_skills` as tools. Each tool
  declares a full `inputSchema` **and** `outputSchema` (with per-field
  descriptions and a human title), so any client can discover its exact
  request/response shape. The server negotiates the MCP `protocolVersion` on
  `initialize` and answers `ping`. A zero-dependency conformance suite
  (`tooling/tests/test_mcp_conformance.py`, validator in
  `tooling/jsonschema_mini.py`) verifies the handshake, discovery, and that
  every tool's live output matches its declared `outputSchema` — so behavior is
  consistent across clients. This is the primary cross-model bridge.
- **Skill-based runtimes (Codex, Claude Code):** install the Markdown skills
  with `bin/bootstrap-skills.sh --runtime <codex|claude|generic>`. Skill content
  is model-agnostic; only the install directory differs per runtime
  (`tooling/runtime_targets.py`). Override with `--dest` or `AI_EFF_SKILLS_DEST`.
- **Provider tool adapters (OpenAI, DeepSeek, Anthropic, Gemini):** the same six
  tools are exposed in each provider's native function-calling format via thin
  adapters in `tooling/adapters/`. A single canonical registry
  (`tooling/tool_registry.py`, `TOOL_SPECS`) is the source of truth that both the
  MCP server and the adapters consume, so declarations never drift. Each adapter
  does two things and nothing else: `tool_declarations()` builds the provider's
  native tool list, and `parse_tool_call()` turns a provider tool-call back into
  a canonical `(name, arguments)` pair dispatched through
  `AiEfficiencyMcpServer.invoke`. The Gemini adapter additionally sanitizes the
  JSON Schema into Gemini's OpenAPI subset (drops `additionalProperties`, rewrites
  nullable unions, uppercases types). Emit or dispatch via
  `bin/provider-tools.sh --provider <p> --list` / `--call <tool> --arguments '<json>'`.
  Adapters make no network calls and import no SDKs — they only shape requests and
  parse responses, preserving the zero-runtime-dependency guarantee.
- **Raw-API models without function calling:** the task package produced by
  `build_task_package` (`package.md`) is a self-contained, model-agnostic
  **context pack** — inject it directly into the model's prompt. Emit one with
  `bin/context-pack.sh --project <p> --requirement "<text>"` (prints to stdout,
  or `--out FILE`); back it with `tooling/context_pack.py`.

Adding a new runtime is mostly a matter of adding an entry to `RUNTIMES` in
`tooling/runtime_targets.py` (skills directory + label). Adding a new tool
provider is one adapter file plus an entry in `tooling/adapters/__init__.py`.

## Business Onboarding

Maestro onboards a project through a machine-checkable pipeline so the system
can validate readiness before work starts:

- **`playbook.json`** (`tooling/playbook_schema.py`) — a validated JSON Schema
  contract for project-specific guidance (keywords → suspected modules, risk
  flags, recommended checks). The schema is enforced by `validate_playbook()`;
  malformed guidance is caught at validation time, not at task-build time.
- **Structured business card** (`tooling/business_card.py`) — a machine-readable
  `business-card.json` that sits alongside the human-friendly
  `business-context.md`. Validated against `BUSINESS_CARD_SCHEMA`, rendered to
  markdown via `card_to_markdown()`.
- **Project-type discovery** (`tooling/project_types.py`) — scans
  `project-types/` directories and returns typed metadata (description, rules,
  pitfalls), listable via CLI and MCP tool.
- **Guided onboarding** (`tooling/onboard_project.py`) — one command that
  registers the project shell, generates a starter playbook and business card,
  and prints a readiness report. Exposed as the `register_project` MCP tool
  plus the new `validate_project` and `list_project_types` MCP tools.
- **Validation** (`tooling/validate_project.py`) — checks canonical files,
  playbook validity, business card validity, and project-type membership.

After onboarding (✅ all checks), the project is ready for memory-read-first
task work through `build_task_package`.

## Orchestration Runtime

Maestro includes a deterministic workflow engine (`tooling/workflow_engine.py`)
that executes multi-step tool pipelines without calling any LLM:

- **Workflow definition** — a JSON step DAG with `id`, `tool`, `args`,
  `depends_on` (dependency list), optional `verify` (gate condition), and
  `retry` (max_attempts).
- **State machine** (`tooling/workflow_state.py`) — each step tracks a proper
  lifecycle (pending → in_progress → verifying → completed | failed; retry
  loops back). The engine enforces valid transitions; aggregate workflow state
  is computed from step states.
- **Deterministic execution** — the engine resolves the DAG, runs independent
  steps in parallel (`concurrent.futures`), and dispatches every step through
  `server.invoke()` (the same canonical path as MCP and adapters). Failed steps
  block dependents; retries re-enter the pool.
- **Built-in verbs** — `fan_out` runs an array of tool calls in parallel;
  `gate_check` with conditions (`always_pass`, `always_fail`, `no_error`,
  `output_not_empty`) gates step progression.
- **MCP tools** — `run_workflow` and `get_workflow_status` are exposed so any
  connected model can trigger and monitor workflows.

The workflow engine is how Maestro graduates from "toolbox" to "autopilot":
steps, ordering, parallelism, and lifecycle are deterministic infrastructure,
and the LLM supplies the intelligence (what steps, in what order).

## Dashboard

Maestro ships with a local web dashboard (`bin/dashboard.sh` — starts on
port 8420, opens browser automatically):

- `tooling/api_server.py` — stdlib `http.server` JSON REST API (zero new deps)
  wrapping `AiEfficiencyMcpServer`. Endpoints: `/api/projects` CRUD,
  `/api/tools` list+invoke, `/api/workflows/run`, `/api/memory` search,
  `/api/project-types`, `/api/health`.
- `tooling/ui/dashboard.html` — single-page app (vanilla JS + CSS, no build
  step, no npm): four tabs — Projects (list + detail + onboard modal), Tools
  (dynamic form + invoke), Workflows (JSON editor + presets + step results),
  Memory (search + patterns/rules browse). Dark theme, works at 1024px+.

The dashboard is the visual answer to "命令会记不住" — everything is
clickable, browsable, and live-validated.

## Agent-to-Agent Handoff (A2A)

When one agent fails mid-task (network issue, model unavailable, crash),
another agent can resume precisely where the first left off:

- **Checkpoints** (`tooling/checkpoint.py`) — every agent records a structured
  checkpoint at each step: what it did, what it produced, what files changed,
  and what should happen next. Stored as append-only JSON under
  `runtime/task-runs/<project>/<slug>/checkpoints/`.
- **Agent identity** — `update_task_run_state` records which agent made each
  state transition. Checkpoints carry the agent name. The system tracks who
  did what, when.
- **Resume** (`resume_task` MCP tool) — given a project + task_slug, returns
  a complete context snapshot: agent history, completed steps with summaries,
  files modified, next-step hint, and a self-contained `resume_context_pack`
  (markdown) injectable directly into any agent's prompt.
- **Handoff** (`handoff_task` MCP tool) — explicit agent-to-agent handoff
  with a checkpoint and state transition to `handed_off`.

This prevents dead loops (agent B redoing what A already did), memory
corruption (two agents writing conflicting notes), and semantic drift
(agent B misunderstanding the intent).

## Extending Maestro

- **New project type:** add a folder under `project-types/`.
- **New project:** `tooling/onboard_project.py`, then enrich the cards.
- **New skill:** add a thin skill under `skills/`, back it with tooling.
- **New backend capability:** add a module under `tooling/` with tests.
- **New runtime:** extend `RUNTIMES` in `tooling/runtime_targets.py`.

See [ROADMAP.md](ROADMAP.md) for where this is heading.
