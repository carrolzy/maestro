---
name: verification-before-close
description: Use when implementation or analysis is about to be declared complete for a registered project and verification, task state, or closeout status still needs to be made explicit. Also use when automation mode requires a task to record verified, pending-closeout, or closed state before completion claims.
---

# Verification Before Close

## Overview

This skill enforces the local rule that a task should not be treated as done until verification and closeout state are explicit.

It is a verification and lifecycle-state skill.
It should determine what must be verified, capture whether verification happened, update task-run state, and distinguish verified work from fully closed work.
It should not pretend that closeout is complete when write-back or sync is still pending.

## Use This Skill When

- the worker is about to say the task is done
- implementation has changed code or behavior and should be verified
- a task run state needs to move forward
- a project in automation mode expects explicit closeout discipline

Do not use this skill for:

- early exploration before implementation stabilizes
- unfinished work that is clearly still in progress
- trivial questions with no task lifecycle implications

## Required Inputs

- `project`
- `task-slug`

Optional inputs:

- `project-type`
- `verification-command`
- `verification-notes`
- `runtime-root`

If the project type is not supplied, derive it from known project context when possible.
If it cannot be derived safely, fall back to project-specific checks or ask explicitly.

## Source Of Truth

Use these sources:

- `project-types/<type>/verification.md`
- project-specific context in `projects/<project>/`
- automation-mode rules when they exist
- `tooling/update_task_run_state.py`
- `runtime/task-runs/<project>/<task-slug>/status.json`

## Required Workflow

1. Confirm the project and task slug.
2. Determine the verification basis:
   - explicit verification command
   - project-type verification checklist
   - project-specific known verification focus
3. Require at least one concrete verification artifact:
   - command run
   - manual check result
   - explicit verification note
4. Decide the current lifecycle state:
   - `verified` if implementation-level verification is complete
   - `pending-closeout` if implementation is done but write-back or sync is still pending
   - `closed` only if verification and required closeout are both complete
5. Workspace hygiene check (before `closed`):
   - list helper files this task created in the business repo (test probes,
     debug scripts, one-off verification files)
   - each must be either registered via `register_temp_file` (with a TTL),
     deleted now, or explicitly promoted to a tracked permanent file
   - unregistered throwaway files in the business repo block `closed`
   - any file this task ADDED to a test directory must state why the
     module's existing test file could not be extended; task-style names
     (-fix/-final/-v2/date) block `closed` — merge into the canonical test
     file or move to scratch (`audit_tests` reports offenders)
   - see the `workspace-hygiene` skill for placement rules
6. Update the task-run state with `tooling/update_task_run_state.py`.
7. Report the current state and what remains before full closeout.

## Verification Basis

Prefer explicit evidence over generic checklists.

Use this order:

1. user-supplied verification command or result
2. project-specific known checks from project context or task package
3. project-type checklist from `project-types/<type>/verification.md`

The project-type checklists are minimum guidance, not proof by themselves.
Do not mark a task verified unless at least one real verification action has occurred.

## Task State Rules

Use these meanings:

- `verified`: implementation-level verification completed
- `pending-closeout`: implementation happened but write-back or sync is still incomplete
- `closed`: verification, write-back, and sync are all complete when required by the workflow

If the project is under automation mode, do not skip from “implemented” to `closed` unless closeout is fully complete.

## Preferred Command

Use this backend pattern to update lifecycle state:

```bash
cd "${AI_EFF_SYSTEM_ROOT:-$HOME/workspace/ai-efficiency-system}"
PYTHONPATH=tooling python3 -c '
from pathlib import Path
from update_task_run_state import update_task_run_state
print(update_task_run_state(
    runtime_root=Path(".").resolve() / "runtime",
    project="<project>",
    task_slug="<task-slug>",
    state="<state>",
))
'
```

Use the smallest valid state transition.
Do not jump straight to `closed` if intermediate closeout requirements are still pending.

## Response Contract

Return a short summary with:

- what was verified
- what evidence exists
- which lifecycle state was recorded
- what remains before full closeout, if anything
- the path to the updated `status.json`

Keep the summary short and explicit.

## Failure Rules

If no concrete verification happened:

- do not mark the task `verified`
- say verification is still missing
- point to the relevant project-type or project-specific checks

If the project type is unknown and no explicit verification command is provided:

- do not guess a fake checklist
- fall back to project-specific context or ask for the verification basis

If state update fails:

- report verification findings separately from state persistence
- do not claim the lifecycle record was updated

If write-back or sync is still pending:

- do not mark the task `closed`
- use `pending-closeout` when implementation is otherwise done

## Current Local Constraints

- there is no single wrapper yet for verify -> write-back -> sync -> close
- project-type guidance exists, but executable command mapping is incomplete
- automation mode is still a pilot, not a universal task-entry and closeout system
- closeout truth still depends on honest reporting of what actually happened

## Backend References

- `tooling/update_task_run_state.py`
- `project-types/admin-dashboard/verification.md`
- `project-types/chrome-extension/verification.md`
- `project-types/node-automation/verification.md`
- `project-types/uniapp-mini-program/verification.md`
