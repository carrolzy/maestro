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
- **Raw-API models (Gemini, DeepSeek, …):** the task package produced by
  `build_task_package` (`package.md`) is a self-contained, model-agnostic
  **context pack** — inject it directly into the model's prompt. Emit one with
  `bin/context-pack.sh --project <p> --requirement "<text>"` (prints to stdout,
  or `--out FILE`); back it with `tooling/context_pack.py`.

Adding a new runtime is mostly a matter of adding an entry to
`RUNTIMES` in `tooling/runtime_targets.py` (skills directory + label).

## Extending Maestro

- **New project type:** add a folder under `project-types/`.
- **New project:** `tooling/register_project.py`, then enrich the cards.
- **New skill:** add a thin skill under `skills/`, back it with tooling.
- **New backend capability:** add a module under `tooling/` with tests.
- **New runtime:** extend `RUNTIMES` in `tooling/runtime_targets.py`.

See [ROADMAP.md](ROADMAP.md) for where this is heading.
