# Memory

This directory stores reusable execution memory for Maestro.

It starts almost empty on purpose: as you use Maestro on your own projects,
`projects/<project>/` fills with your cases, and the most reusable lessons get
promoted into `patterns/` and `rules/`. The compounding value is yours.

> **Seed examples:** the entries currently in `patterns/` and `rules/` are
> illustrative seeds that show the format. They are safe to delete — your own
> memory will replace them over time.

## Layout

- `projects/<project>/cases/`: project-specific incidents and task outcomes (local, accumulates as you work)
- `projects/<project>/index.md`: project memory index
- `patterns/`: reusable patterns across projects
- `rules/`: standing rules promoted from repeated incidents

## Source of Truth

Raw task write-backs are still authored in Obsidian first.

This memory layer is the curated operational mirror used by the local AI efficiency system.

## Sync Rule

After non-trivial work:

1. write back to Obsidian
2. sync the note into project memory
3. decide whether to promote a pattern or rule

## Search

Use `bin/search-memory.sh` to inspect project cards, recent cases, patterns, and rules before starting non-trivial work.
