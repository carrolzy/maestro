# Maestro Roadmap

Maestro began as a personal set of reusable AI execution assets (memory,
project-type templates, rules, skills, task packages). The goal is to evolve it
into an **agent orchestration product**: a model-agnostic system that any LLM
can plug into and use to serve arbitrary business projects.

The published repository is the **framework baseline**. Real business projects,
their memory, and their runtime artifacts stay local and are never committed.

## North Star

A business can onboard by describing itself once (a business card + a playbook),
and any connected model can then plan, execute, verify, and write back work
against that business — with reusable memory and standing rules carried across
tasks.

## Phases

### Phase 0 — Reusable asset library (done / baseline)
- Layered memory (`memory/{projects,patterns,rules}`)
- Project-type templates (`project-types/`) and copy-ready templates (`templates/`)
- Skills for intake, registration, memory-first reads, verification, and write-back
- Task-package builder and task-run lifecycle state
- Pluggable, business-free guidance via per-project `playbook.json`

### Phase 1 — MCP tool layer (in progress)
- `tooling/ai_efficiency_mcp_server.py` exposes the core operations as MCP tools
  (`search_memory`, `build_task_package`, `register_project`,
  `update_task_run_state`, `writeback_and_sync_memory`, `doctor_local_skills`)
- ✅ Every tool declares `inputSchema` + `outputSchema` with per-field
  descriptions and a title; `initialize` negotiates `protocolVersion`; `ping`
  is supported
- ✅ Zero-dependency conformance suite validates handshake, discovery, and that
  each tool's live output matches its declared schema
  (`tooling/tests/test_mcp_conformance.py`, `tooling/jsonschema_mini.py`)
- ✅ `bin/context-pack.sh` emits a model-agnostic context pack for raw-API models

### Phase 2 — Model-agnostic adapter layer (in progress)
- ✅ Single canonical tool registry (`tooling/tool_registry.py`, `TOOL_SPECS`) is
  the source of truth consumed by both the MCP server and the adapters; the
  server gained `invoke()` for unwrapped canonical dispatch
- ✅ Thin per-provider adapters (`tooling/adapters/`) translate the same six
  tools into each provider's native function-calling format and parse tool-calls
  back to a canonical `(name, arguments)` — covering **OpenAI, DeepSeek,
  Anthropic, Gemini** (Gemini includes an OpenAPI-subset schema sanitizer)
- ✅ `bin/provider-tools.sh` lists native declarations and dispatches calls;
  `tooling/tests/test_adapters.py` checks declaration coverage and round-trip
  dispatch validated against each tool's `outputSchema`
- No business logic in adapters, no SDK/network deps (pure translation)
- Next: standardize multi-turn tool-result framing per provider (toward Phase 4)

### Phase 3 — Pluggable business onboarding
- A business is fully described by tracked, generic-shaped config:
  business card + `playbook.json` + project-type selection
- No business specifics in core code (the `playbook.json` mechanism is the first
  step toward this)
- Self-serve onboarding flow + validation

### Phase 4 — Orchestration runtime
- Deterministic multi-step orchestration (plan → execute → verify → write back)
- Parallel fan-out for independent subtasks, with verification gates
- Lifecycle state, retries, and closeout as first-class concepts

### Phase 5 — Product surface
- Service/web packaging, multi-tenant isolation, observability
- Marketplace of project-type templates and reusable patterns

## Design Principles

- **Business stays out of core.** Generic engine + per-project config only.
- **Memory before work.** Read prior context before starting; write back after.
- **Verify before close.** No task is closed without evidence.
- **Local-first boundaries.** Real project data never leaves the user's machine
  unless they explicitly choose to.
