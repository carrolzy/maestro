# Memory AI

## Purpose

Memory AI is the layer that turns task write-backs into reusable operating context for future work.

It is not just note storage.

It should provide:

1. automatic sync after non-trivial tasks
2. stable storage inside the AI efficiency system
3. retrieval before future work starts
4. promotion of useful incidents into reusable patterns or rules

## Memory Tiers

### 1. Project Memory

Location:

- `memory/projects/<project>/cases/`

Use for:

- project-specific incidents
- root causes tied to one codebase
- local architecture decisions
- debugging timelines

### 2. Pattern Memory

Location:

- `memory/patterns/`

Use for:

- reusable implementation patterns
- debugging heuristics
- UI/interaction tactics
- state-management lessons that apply across projects

### 3. Rule Memory

Location:

- `memory/rules/`

Use for:

- standing operating rules
- repeated non-negotiable safeguards
- process changes that should affect future execution

## Lifecycle

1. task completes
2. write back to Obsidian, preferably through `tooling/writeback_and_sync_memory.py`
3. sync into `memory/projects/<project>/cases/`
4. if reusable, manually or automatically promote to:
   - `memory/patterns/`
   - `memory/rules/`

## Retrieval Order

Before non-trivial work:

1. project business context
2. project overrides
3. recent project memory cases
4. relevant reusable patterns
5. standing rules

## Minimal Operating Rule

For all non-trivial project work:

- write back to Obsidian
- sync to efficiency system memory

Preferred single entry:

- `tooling/writeback_and_sync_memory.py`

For all recurring incidents:

- promote at least one reusable pattern
