# Memory Execution Flow

## Before Work

For non-trivial tasks:

1. read `projects/<project>/business-context.md`
2. read `projects/<project>/project-override.md`
3. read recent `memory/projects/<project>/cases/`
4. read matching `memory/patterns/`
5. read matching `memory/rules/`

## After Work

1. verify the implementation
2. write back to Obsidian
3. run `tooling/sync_latest_project_memory.sh <project>`
4. sync the note into `memory/projects/<project>/cases/`
5. decide whether to promote a pattern
6. decide whether to promote a rule

## Minimal Command

```bash
tooling/sync_latest_project_memory.sh <project>
```

## When To Promote

Promote to `patterns/` when:

- the tactic is reusable
- the bug class is general
- the UI or state pattern can recur

Promote to `rules/` when:

- the same safeguard should become default behavior

## Minimal Human Burden

The user should not need to manually re-explain completed work for system memory upkeep.

The local agent workflow should:

- archive task memory automatically
- keep the project mirror current
- preserve local-only boundaries
