---
name: writing-plans
description: Use after a design is confirmed (via brainstorming or an explicit user spec) and before implementation starts on multi-step work. Breaks the design into small, independently verifiable tasks with exact file paths and verification steps, saved as a plan document that implementation then follows task by task.
---

# Writing Plans

## Overview

A confirmed design says *what* to build; a plan says *in which order, in what
increments, verified how*. Small increments with per-task verification catch
mistakes at the task boundary instead of at the end, and make the work
resumable by any agent (or after any interruption) via the A2A checkpoint
chain.

This skill produces a plan document. It never produces code.

## Use This Skill When

- a `brainstorming` design document exists and implementation is next
- the user supplies a complete spec and asks to implement something multi-step
- work will touch more than 2-3 files or take more than one sitting

Do not use this skill for:

- single-file, single-step changes — plan overhead exceeds the work
- exploratory spikes whose outcome decides whether there will be a plan at all

## Task Granularity Standard

Each task should be **one focused change, verifiable on its own** — as a rule
of thumb, minutes of work, not hours. A task MUST have:

1. **Title** — imperative, specific ("Add TTL refresh on task close", not
   "Update state handling")
2. **Files** — exact paths to create or modify
3. **Change description** — what changes in each file (signatures, behavior,
   key logic), detailed enough that no design decisions remain
4. **Verification** — the command to run or check to perform, and what
   passing looks like (e.g. `PYTHONPATH=tooling python3 -m unittest
   tests.test_x` green; or a grep proving the wiring exists)
5. **Dependencies** — which prior tasks it needs, if any

If a task description needs the word "and" more than twice, split it.
If a task cannot be verified without finishing three other tasks, restructure.

## Required Workflow

1. Read the design document (or user spec) fully. If it leaves design
   decisions open, stop and route back to `brainstorming` — a plan must not
   make design decisions silently.
2. For each area the design touches, verify current code reality with the
   `agentic-search` loop (files move; the design may cite stale paths).
   Plans reference verified `file:line` reality, not memory.
3. Break the work into ordered tasks per the granularity standard. Prefer an
   order where each task leaves the system green (tests passing, nothing
   half-wired).
4. Mark independent tasks explicitly — they can fan out to parallel agents or
   `run_workflow` steps later.
5. End the plan with a **final verification** section: full test suite,
   preflight, and any end-to-end check from the design's verification plan.
6. Save to `docs/superpowers/plans/<date>-<slug>-implementation-plan.md`
   (Maestro work) or the project's equivalent. Present the task list summary
   to the user for approval before implementation begins.

## Plan Document Skeleton

```markdown
# <Title> Implementation Plan

Design: <path to design doc>

## Task 1: <imperative title>
- Files: path/a.py, path/b.py (new)
- Change: <what changes, precisely>
- Verify: <command + expected result>
- Depends on: —

## Task 2: ...

## Final Verification
- <full suite command>
- <end-to-end check>
```

## Execution Contract

During implementation, work strictly task by task: mark the task in progress
(TaskCreate/TaskUpdate or the plan checkboxes), implement, **run its
verification before starting the next task**, checkpoint. A failed
verification blocks progression — fix or consciously revise the plan; never
skip ahead over a red task.

## Failure Rules

- A plan whose tasks average "about an hour each" is a design outline, not a
  plan — decompose further.
- If reality-checking (step 2) contradicts the design, surface the conflict
  and update the design first; do not plan against fiction.
- Do not pad trivial work into ceremony: if decomposition yields exactly one
  task, say so and implement directly.
