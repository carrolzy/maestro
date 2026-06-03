---
name: project-intake
description: Use when a new requirement for a registered project is about to enter implementation, especially when the worker needs to assemble project context, memory, and a task package before coding starts. Also use when a project is in automation mode and implementation must not begin without a generated task package.
---

# Project Intake

## Overview

This skill turns a new project requirement into a stable pre-execution artifact.

Use it to enforce the local rule that non-trivial implementation should begin from a task package rather than from ad hoc chat context.

This skill is an orchestration layer.
It should read project context, invoke the existing builder, and summarize the result.
It should not reimplement task-package logic inside the skill.

## Use This Skill When

- the user gives a new feature, bugfix, or refactor requirement for a registered project
- implementation is about to begin
- the task is non-trivial and should have a structured package first
- the project has automation-mode rules that require task packaging before coding

Do not use this skill for:

- trivial file questions
- post-implementation closeout
- a diagnostics case that already has its own case directory handoff

## Required Inputs

- `project`
- `requirement`

Optional inputs:

- `slug`
- `product-doc-path`
- `dev-doc-path`
- `output-root`
- `runtime-root`
- `vault-root`
- `note-path`
- `memory-root`
- `task-slug`

If the user does not supply a project slug and the correct project cannot be inferred safely from local repo context, stop and ask for the project explicitly.

## Source Of Truth

Read from these sources in this order:

1. `projects/<project>/business-context.md`
2. `projects/<project>/project-override.md`
3. `projects/<project>/task-context.md`
4. `projects/<project>/dev-docs/` when a development technical document exists
5. relevant `memory/projects/<project>/cases/`
6. relevant `memory/patterns/`
7. relevant `memory/rules/`

The builder may perform part of this assembly itself.
Your job is to ensure the task does not skip the intake boundary.

## Required Workflow

1. Confirm the project exists under `projects/`.
2. Read the project context files and check whether the project defines automation-mode constraints.
3. If a product document is supplied or referenced and no development technical document exists yet, generate one before task packaging:
   - read the product document
   - inspect only enough project code to ground affected pages/modules
   - write the document to `projects/<project>/dev-docs/<YYYY-MM-DD>-<slug>-frontend-tech-design.md`
   - keep business repositories free of temporary dev-docs
   - include resolved decisions, open questions, affected files, API expectations, and verification focus
4. If a development technical document already exists, pass it to the builder with `--dev-doc-path`.
5. If the project requires task packaging before implementation, treat package generation as mandatory.
6. Run the builder through `tooling/build_task_package.py`.
7. Surface the output directory.
8. Read the generated `package.json` and `package.md`.
9. Summarize only the highest-signal outputs:
   - suspected modules
   - recommended verification focus
   - risk flags
   - open questions
   - development technical document path when supplied
10. If builder execution fails and packaging is mandatory, do not proceed into implementation.

## Builder Command

Use this backend command pattern:

```bash
cd /Users/apple/Downloads/workspace/ai-efficiency-system
PYTHONPATH=tooling python3 tooling/build_task_package.py \
  --project "<project>" \
  --requirement "<requirement>"
```

Add optional flags only when they are needed:

- `--slug`
- `--output-root`
- `--runtime-root`
- `--vault-root`
- `--note-path`
- `--dev-doc-path`
- `--memory-root`
- `--task-slug`

## Expected Outputs

The builder should emit:

- `runtime/task-packages/<project>/<YYYY-MM-DD>-<slug>/package.json`
- `runtime/task-packages/<project>/<YYYY-MM-DD>-<slug>/package.md`

These are runtime artifacts, not Obsidian notes.

## Response Contract

After a successful run, report:

- the generated package path
- whether packaging is mandatory for this project
- the development technical document path, if one was generated or supplied
- the most relevant modules or files to inspect next
- the top verification focus
- any unresolved questions or weak evidence

Keep the summary short.
The package artifact is the detailed handoff boundary.

## Failure Rules

If the project is unknown:

- stop
- report that the project is not registered
- point to `projects/README.md` as the registration contract

If builder output is incomplete:

- stop implementation from proceeding under automation mode
- say what is missing
- do not fabricate package content manually

If evidence is weak:

- preserve uncertainty explicitly
- keep multiple candidate modules instead of pretending certainty

## Current Local Constraints

- project-type identification is still thin
- task-entry triggering is not yet universal
- fallback behavior for weak matches is conservative by design
- this skill depends on local repo paths and existing builder tooling

## Backend References

- `tooling/build_task_package.py`
- `tooling/task_package_builder.py`
- `projects/README.md`
- `docs/system-specs/2026-05-19-general-intake-task-package-builder-design.md`
