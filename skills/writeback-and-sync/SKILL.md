---
name: writeback-and-sync
description: Use when route_task has selected Maestro L2 or L3 and completed project work should be archived into Obsidian and mirrored into local memory, or when the user explicitly asks to document, archive, sync, or preserve a result.
---

# Writeback And Sync

## Overview

This skill enforces the local rule that durable task knowledge should be written back once and then mirrored into project memory.

It is a closeout orchestration skill.
It should decide whether write-back is warranted, ensure the note shape is acceptable, invoke the local write-back wrapper, and report the synced result.
It should not reimplement note sync logic inside the skill.

## 等级适用

以 `route_task` 返回等级为准：

- L0/L1 默认跳过本 Skill，除非用户明确要求归档，或结果形成了应长期保留的稳定规则。
- L2/L3 默认执行写回与同步；L3 的外部副作用确认必须在写入前完成。
- 任何等级都不得把噪声、未验证结论或完整敏感 Prompt 写入持久记忆。

## Use This Skill When

- `route_task` selected L2 or L3 and implementation is finishing
- a debugging path, design decision, or reusable fix should be archived
- the user asks to document, archive, sync, or write back the result
- a project in automation mode expects write-back by default

Do not use this skill for:

- trivial edits with no durable value
- incomplete work where the note would create misleading history
- tasks that belong only in temporary chat context

## Required Inputs

- `project`
- `note-path`
- `source-file`

Optional inputs:

- `slug`
- `append`
- `vault-root`
- `memory-root`

If no note path is supplied, derive one from the default convention:

- `project-notes/codex-auto/<project>/<YYYY-MM-DD>-<slug>.md`

If no safe slug can be inferred, ask for one or use a conservative task slug already established elsewhere in the task.

## Source File Placement

For a registered project, prepare the Markdown source record under the AI
efficiency system root at
`projects/<project>/dev-docs/<YYYY-MM-DD>-<slug>-change-record.md` before
calling the write-back wrapper. Do not create task records, agent notes, or
process documents in the business repository unless the user explicitly asks
for a repository document.

## Source Of Truth

Use these local sources:

- `base/obsidian-writeback.md`
- the note template used by the current local Obsidian workflow
- `tooling/writeback_and_sync_memory.py`
- `tooling/writeback_and_sync_memory.sh`

Obsidian is the durable note source of truth.
`memory/projects/<project>/cases/` is the curated operational mirror.

## Required Workflow

1. Decide whether the work is worth durable write-back.
2. Confirm the project slug is valid.
3. Confirm the markdown source file exists under the AI efficiency system for
   registered projects.
4. Confirm the note contains the minimum useful sections:
   - Request
   - Context Used
   - Implementation
   - Verification
   - Risks / Follow-up
   - File References
5. Derive or confirm the target note path.
6. Run the local write-back wrapper.
7. Report:
   - note path written
   - synced project memory case path
   - updated project index path
8. Remind the worker to decide whether the case should be promoted into:
   - `memory/patterns/`
   - `memory/rules/`

## Preferred Command

Prefer this wrapper:

```bash
cd /Users/apple/Downloads/workspace/ai-efficiency-system
tooling/writeback_and_sync_memory.sh "<project>" "<note-path>" "<source-file>"
```

Use the Python entry directly when you need explicit control:

```bash
cd /Users/apple/Downloads/workspace/ai-efficiency-system
python3 tooling/writeback_and_sync_memory.py \
  --vault-root "<vault-root>" \
  --project "<project>" \
  --note-path "<note-path>" \
  --source-file "<source-file>"
```

Add optional flags only when needed:

- `--slug`
- `--append`
- `--memory-root`

## Response Contract

After a successful run, report:

- where the Obsidian note was written
- where the synced case file was created
- whether the project memory index was updated
- whether pattern or rule promotion should be considered

Keep the response short.
The synced case path is the operational handoff artifact.

## Failure Rules

If the source markdown file does not exist:

- stop
- report the missing source file path
- do not create an empty note

If the note content is missing core sections:

- stop and say the note is not ready for durable write-back
- ask for the missing sections to be completed before sync

If the project is unknown:

- stop
- report that the project is not registered
- point to `projects/README.md`

If write-back succeeds but sync fails:

- report both facts separately
- do not pretend memory is current
- surface the exact failed boundary so the user can retry safely

## Current Local Constraints

- vault path handling still depends on machine-local setup
- the wrapper assumes the local Obsidian vault configuration exists
- pattern and rule promotion still require explicit judgment
- the skill should not archive noisy or low-value closeout notes

## Backend References

- `base/obsidian-writeback.md`
- `tooling/writeback_and_sync_memory.py`
- `tooling/writeback_and_sync_memory.sh`
- `memory/README.md`
- `projects/README.md`
