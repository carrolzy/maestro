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
- Goal: a clean, documented tool surface any MCP-capable client can call
- Next: tool schemas, capability discovery, and a conformance test suite

### Phase 2 — Model-agnostic adapter layer
- Thin adapters so the same tools work across model/runtime providers
  (Claude, others) without business logic leaking into the core
- Standardize the request/response contracts and structured outputs

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
