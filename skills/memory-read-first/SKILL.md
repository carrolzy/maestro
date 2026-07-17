---
name: memory-read-first
description: Use when a non-trivial task for a registered project needs prior context before implementation or analysis starts, especially for bugfixes, refactors, feature work, or investigations where project cards, prior cases, reusable patterns, or standing rules may reduce repeated explanation.
---

# Memory Read First

## Overview

This skill enforces the local rule that non-trivial project work should begin from existing project memory rather than from fresh chat context alone.

It is a read-order and summarization skill.
It should gather the minimum high-signal project context before work starts.
It should not invent retrieval logic that does not exist locally.

## Use This Skill When

- the user asks for a bugfix, refactor, feature, investigation, or architecture adjustment in a registered project
- the task is non-trivial
- the project already has cards or memory
- prior incidents or standing rules may affect the current task

Do not use this skill for:

- one-line edits with no project context dependency
- isolated tool usage unrelated to a registered project
- post-implementation write-back or sync

## Required Inputs

- `project`

Optional inputs:

- `requirement`
- `max-cases`

If the project is not known and cannot be inferred safely, stop and ask for the project explicitly.

## Source Of Truth

Use these sources in this fixed order:

1. `projects/<project>/business-context.md`
2. `projects/<project>/project-override.md`
3. recent `memory/projects/<project>/cases/`
4. matching `memory/patterns/`
5. matching `memory/rules/`

This order comes from `base/memory-execution-flow.md`.
Do not skip directly to patterns or rules before project-specific context is read.

## Required Workflow

1. Confirm the project exists under `projects/`.
2. Read `projects/<project>/business-context.md`.
3. Read `projects/<project>/project-override.md`.
4. Read the most recent project cases if they exist.
5. Read matching reusable patterns.
6. Read matching standing rules.
7. Produce a short read-set summary for the current task.
8. Recall-verification bridge: recalled memory describes the *past*. Before
   any recalled `file:line` reference, function name, or code-shape claim
   drives an implementation decision, verify it against the *live* working
   tree with `grep_code` (see the `agentic-search` skill). If the code moved
   or changed, note the drift so the eventual write-back corrects the memory.

## Matching Rules

V1 should stay conservative.

Use simple local heuristics:

- recent project cases by recency
- pattern matches by keyword overlap with the requirement when available
- rule matches by keyword overlap with the requirement when available

If no requirement is supplied:

- prefer recent project cases
- always include the project business card and override
- only include patterns or rules that are obviously relevant from titles or first lines

Do not over-claim retrieval confidence.

## Suggested Read Set Limits

Default limits:

- always read `business-context.md`
- always read `project-override.md`
- read up to `3` recent project cases
- read up to `2` matching patterns
- read up to `2` matching rules

Keep the pre-work context small enough that the worker can still act on it.

## Response Contract

Return a short structured summary with:

- required reads
- optional reads
- the most relevant prior incidents
- the most relevant reusable pattern, if any
- the most relevant standing rule, if any
- the main risks that should shape implementation

Do not dump long raw note content unless the user explicitly asks for it.

## Failure Rules

If the project is unknown:

- stop
- report that the project is not registered
- point to `projects/README.md`

If project memory is sparse:

- say so explicitly
- still return project card and override as the minimum context set
- do not pretend there is prior memory coverage

If no relevant pattern or rule matches:

- say no strong match was found
- do not force weak matches into the read set

## Current Local Constraints

- memory volume is still small
- pattern and rule promotion remains manual
- retrieval is BM25 + optional embeddings via `search_memory`; live-code
  questions route to agentic search instead (see `agentic-search`)

## Backend References

- `base/memory-execution-flow.md`
- `memory/README.md`
- `projects/README.md`
- `docs/system-specs/2026-05-19-local-skill-stack-v1.md`
- `skills/agentic-search/SKILL.md`
