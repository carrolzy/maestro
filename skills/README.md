# Local Skills

This directory stores the repo-local source versions of the first AI efficiency system skills.

These files are not yet the globally installed production skills.
They are the system-owned drafts that define the intended long-term workflow boundary for this repository.

## Current Skill Stack

**Lifecycle skills** (task entry/exit discipline):

- `project-intake`
- `memory-read-first`
- `writeback-and-sync`
- `verification-before-close`
- `project-register`
- `workspace-hygiene`
- `agentic-search`

**Methodology skills** (implementation-process discipline):

- `brainstorming`
- `writing-plans`
- `test-driven-development`
- `systematic-debugging`

## Why These Four

These four skills map directly onto the core workflow defined in the root `README.md`:

1. build a task package before implementation
2. read project memory before non-trivial work
3. verify before claiming completion
4. write back and sync durable knowledge

Together they convert the current process from “documented expectations” into “reusable orchestration units.”

## Execution Order

For a normal non-trivial project task, use the stack in this order:

1. `project-intake`
2. `memory-read-first`
3. `brainstorming` — when the requirement is rough or has design choices
4. `writing-plans` — when the work is multi-step
5. implementation work:
   - `test-driven-development` for behavior changes (red → green → refactor)
   - `systematic-debugging` for bugs (reproduce → locate → understand → fix)
   - `agentic-search` for live-code questions
   - `workspace-hygiene` governs where helper files go
6. `verification-before-close`
7. `writeback-and-sync`
8. `verification-before-close` again if closeout state must move from `verified` or `pending-closeout` to `closed`

Steps 3-4 are skippable for trivial, single-step, fully-specified changes —
each methodology skill states its own skip conditions.

## Role Of Each Skill

### `project-intake`

Purpose:

- turn `project + requirement` into a stable task package
- enforce task-entry discipline
- block implementation when packaging is mandatory and missing

Primary backend:

- `tooling/build_task_package.py`
- `tooling/task_package_builder.py`

### `memory-read-first`

Purpose:

- enforce the pre-work reading order
- surface the minimum relevant context from project cards, project memory, patterns, and rules

Primary backend:

- `base/memory-execution-flow.md`
- `projects/*`
- `memory/*`

### `verification-before-close`

Purpose:

- require explicit verification evidence
- record lifecycle state
- distinguish `verified`, `pending-closeout`, and `closed`

Primary backend:

- `tooling/update_task_run_state.py`
- `project-types/*/verification.md`

### `writeback-and-sync`

Purpose:

- write durable closeout notes into Obsidian
- sync the result into local project memory
- keep the project memory mirror current

Primary backend:

- `tooling/writeback_and_sync_memory.py`
- `tooling/writeback_and_sync_memory.sh`

### `workspace-hygiene`

Purpose:

- route throwaway helper files (test probes, debug scripts) to the central
  scratch area `runtime/scratch/<project>/<task-slug>/`
- register must-stay-in-repo temp files with a TTL so artifact GC reclaims them
- keep business repositories from accumulating dead files

Primary backend:

- `tooling/temp_registry.py`
- `tooling/artifact_gc.py`
- `base/retention.json`

### `agentic-search`

Purpose:

- route retrieval: memory RAG for write-once knowledge (past fixes,
  requirements, patterns), agentic live-code search for "what is true now"
- drive the multi-hop loop (orient → anchor → read → hop → stop) with a
  tool-call budget and a file:line evidence contract
- enforce the bridge rule: recalled memory references must be verified
  against the live working tree before they drive code changes

Primary backend:

- `tooling/code_search.py`
- `tooling/search_memory.py` (`target=knowledge|code|auto`)

### `brainstorming`

Purpose:

- refine rough requirements through one-at-a-time questions with options
- explore genuine alternatives with trade-offs and a recommendation
- lock a section-by-section confirmed design before any code is written

Output: `projects/<project>/dev-docs/<date>-<slug>-design.md`

### `writing-plans`

Purpose:

- decompose a confirmed design into small, independently verifiable tasks
  (exact files, change description, verification command, dependencies)
- reality-check the design against live code before planning
- define the execution contract: verify each task before starting the next

Output: `projects/<project>/dev-docs/<date>-<slug>-implementation-plan.md`

### `test-driven-development`

Purpose:

- enforce red → green → refactor for behavior changes
- forbid implementation-before-test (a test that never failed proves nothing)
- route permanent regression tests to the suite, probes to scratch

### `systematic-debugging`

Purpose:

- four phases: reproduce → locate → understand → fix
- iron rule: no changing code whose failure mechanism can't be stated in one
  sentence
- failed fix prediction = wrong understanding → back to locate, never stack
  guesses; escalate after 3 misses with documented findings

## Architectural Boundary

These skills should stay thin.

They should:

- orchestrate the workflow
- enforce sequence
- call backend scripts
- summarize outcomes

They should not:

- duplicate Python logic already implemented in `tooling/`
- become the storage layer for project knowledge
- absorb volatile project details that belong in `projects/`, `project-types/`, or `memory/`

The intended boundary is:

- `skills/`: orchestration and process enforcement
- `tooling/`: executable logic
- `projects/`, `project-types/`, `memory/`: durable context and knowledge
- `runtime/`: generated task packages and task lifecycle state

## Current Status

Current state of these skill files:

- repo-local draft sources exist
- they can now be installed into the global Codex skill directory with `bin/install-local-skills.sh`
- `project-intake` passed round-1 eval and is in limited live trial
- `memory-read-first` passed round-1 eval and is in limited live trial
- `verification-before-close` passed round-1 eval and is in limited live trial
- `writeback-and-sync` passed round-1 eval and is ready for limited live trial after backend alignment
- `project-register` is installed and in sync as the project-shell registration entry point
- some backend flows are still partial, especially around end-to-end closeout orchestration

## Installation

Use the repo-owned installer when you want to copy these source skills into a machine-local Codex runtime directory:

```bash
bin/doctor-local-skills.sh
bin/bootstrap-codex-local.sh
bin/install-local-skills.sh --list
bin/install-local-skills.sh project-intake
bin/install-local-skills.sh --takeover project-intake
bin/install-local-skills.sh --all
```

Default destination:

- `~/.codex/skills`

Behavior:

- installs complete skill directories, not just `SKILL.md`
- writes a source marker so later reinstalls know the target is repo-managed
- refuses to overwrite an existing unmanaged skill directory by default
- `--takeover` allows an explicit one-time replacement of an unmanaged existing directory when you intentionally want to bring it under repo-managed control
- `bin/doctor-local-skills.sh` reports `missing`, `installed`, `drifted`, or `unmanaged`
- `bin/bootstrap-codex-local.sh` installs missing repo-managed skills and repairs drifted ones
- restart Codex after install or reinstall so skills can trigger in new sessions

## Next Recommended Steps

1. Install `writeback-and-sync` into limited live trial to complete the first four-skill stack rollout.
2. Keep live-trial scope narrow while observing the five-skill stack together.
3. Add a wider machine-bootstrap wrapper later if skills, plugins, and config need one-shot setup together.
4. Add drift policy for unmanaged directories only if forced takeover ever becomes necessary.

## File Map

- `skills/project-intake/SKILL.md`
- `skills/memory-read-first/SKILL.md`
- `skills/writeback-and-sync/SKILL.md`
- `skills/verification-before-close/SKILL.md`
- `skills/project-register/SKILL.md`
- `docs/system-specs/2026-05-19-local-skill-stack-v1.md`
- `docs/system-specs/2026-05-20-project-register-design.md`
- `docs/system-plans/project-intake-eval-record-round-1.md`
- `docs/system-plans/memory-read-first-eval-record-round-1.md`
- `docs/system-plans/verification-before-close-eval-record-round-1.md`
- `docs/system-plans/writeback-and-sync-eval-record-round-1.md`
- `docs/system-plans/2026-05-20-project-register-implementation-plan.md`
