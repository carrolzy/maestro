# Memory Layer Bootstrap

This staging bundle adds a minimal Memory AI layer to the local AI efficiency system.

## What It Adds

- `memory/`: durable project memory, reusable patterns, and long-lived rules
- `tooling/sync_obsidian_to_memory.py`: sync one Obsidian write-back note into the efficiency system
- `tooling/sync_project_notes_to_memory.py`: sync the latest N project notes into project memory
- `tooling/sync_latest_project_memory.sh`: daily-use wrapper for latest-note sync
- `tooling/writeback_and_sync_memory.py`: single-entry write-back + memory sync
- `tooling/writeback_and_sync_memory.sh`: shell wrapper for single-entry write-back + sync
- `tooling/search_memory.py`: read-only memory search helper
- `bin/search-memory.sh`: shell wrapper for local memory search
- seeded memory examples for `example-wxapp`
- boundary and governance docs so memory stays local instead of polluting business repos

## Goal

Turn write-back notes from task archives into reusable execution memory that can be:

1. synced automatically after non-trivial work
2. searched before new work starts
3. promoted from project incident -> reusable pattern -> standing rule

## Install Target

Copy these files into your local checkout of this system, for example:

- `$HOME/workspace/ai-efficiency-system/`

## First Sync Example

```bash
python3 tooling/sync_obsidian_to_memory.py \
  --vault-root "$HOME/Documents/my-knowledge-base" \
  --note-path project-notes/codex-auto/example-wxapp/2026-01-01-some-task.md \
  --project example-wxapp \
  --slug some-task
```

## Latest Project Sync Example

Sync the latest one note:

```bash
tooling/sync_latest_project_memory.sh example-wxapp
```

Sync the latest three notes:

```bash
tooling/sync_latest_project_memory.sh example-wxapp 3
```

## Single-Entry Write-Back + Sync Example

```bash
tooling/writeback_and_sync_memory.sh \
  example-wxapp \
  project-notes/codex-auto/example-wxapp/2026-01-01-example.md \
  /tmp/example-note.md
```

## Search Example

```bash
bin/search-memory.sh --project example-wxapp --query "button lock"
```
