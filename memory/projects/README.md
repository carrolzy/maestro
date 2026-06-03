# Project Memory

This directory is **intentionally empty** in a fresh checkout.

As you use Maestro on your own projects, each project gets a folder here that
accumulates its memory:

```
memory/projects/<your-project>/
├── index.md           # project memory index
└── cases/             # synced write-back notes (incidents, task outcomes)
```

These are created and filled automatically by the write-back / sync flow
(`tooling/sync_project_notes_to_memory.py`, `bin/search-memory.sh`). Everything
under `memory/projects/` except this README is treated as private local data
and is never published (see `.gitignore`).

The longer you use Maestro on a project, the richer this memory becomes — which
is what makes the system progressively smarter and more tailored to your work.
