---
name: project-register
description: Use when a new project needs to be registered into the local AI efficiency system, when you need to create the canonical `projects/<project>/` shell before `project-intake` or `memory-read-first` can work, or when the user asks to scaffold a project folder with the standard business-context, override, and task-context files.
---

# Project Register

## Overview

Use this skill to create the canonical project shell for a new project.

This skill is intentionally thin:

- it routes to the local project-registration command
- it does not invent project metadata
- it does not create memory cases or task packages
- it does not install other skills

The backend contract lives in:

- `bin/register-project.sh`
- `tooling/register_project.py`
- `projects/README.md`
- `templates/business-context.md`
- `templates/project-override.md`
- `templates/task-context.md`

## Use This Skill When

- the user says a project is new and should be added to the AI efficiency system
- the user asks to scaffold or register a project folder
- the user wants the canonical project shell created before task intake starts
- the user wants to refresh an existing project shell intentionally with `--force`

Do not use this skill for:

- memory sync
- task packaging
- verification or closeout
- project-specific implementation work after registration

## Required Inputs

- `project`
- `summary`

Optional inputs:

- `project_type`
- `force`

If the user does not give a safe one-sentence summary, ask for one before registering.

## Source Of Truth

Use these local sources:

- `projects/README.md`
- `templates/business-context.md`
- `templates/project-override.md`
- `templates/task-context.md`
- `docs/system-specs/2026-05-20-project-register-design.md`
- `docs/system-plans/2026-05-20-project-register-implementation-plan.md`

## Required Workflow

1. Confirm the project slug is valid and safe to create.
2. Check whether the project already exists under `projects/`.
3. If the project exists and `force` is not set, stop and report that the project is already registered.
4. Call the local registration command.
5. Confirm the command created:
   - `projects/<project>/business-context.md`
   - `projects/<project>/project-override.md`
   - `projects/<project>/task-context.md`
6. If `project_type` was supplied, confirm it is reflected as a hint in the generated task context.
7. Point the user to `project-intake` as the next step for real work.

## Command Contract

Preferred command:

```bash
bin/register-project.sh --project <slug> --summary "<one sentence>" [--project-type <type>] [--force]
```

If `force` is true, pass `--force` explicitly.
Do not imply that `--force` is the normal path.

## Failure Rules

If the slug is malformed:

- stop
- explain the expected slug shape

If the summary is missing or too vague:

- stop
- ask for a one-sentence project summary

If the project already exists and `force` is not set:

- stop
- say the project is already registered

If the registration command fails:

- report the exact failed boundary
- do not pretend the project shell exists

## Response Contract

Return a short summary with:

- the created or refreshed project path
- the three generated files
- whether a project-type hint was included
- the next recommended step (`project-intake`)

Keep the response short and operational.

