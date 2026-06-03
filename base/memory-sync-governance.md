# Memory Sync Governance

## Goal

Keep project knowledge automatically synchronized into the local AI efficiency system without polluting project repositories.

## Source and Target

### Source

- Obsidian write-back notes
- optionally stable project docs when explicitly referenced

### Target

- `memory/projects/<project>/cases/`
- `memory/patterns/`
- `memory/rules/`

## Required Rule

After every non-trivial task:

1. write back to Obsidian
2. use `tooling/writeback_and_sync_memory.py` when possible
3. sync the note into local project memory

## Promotion Rule

Promote a case into a reusable pattern when:

- the lesson applies across multiple projects
- the fix describes a repeatable implementation tactic
- the debugging path is reusable

Promote a case into a standing rule when:

- the same failure mode should always be prevented
- the behavior should alter future execution by default

## Anti-Pollution Rule

Do not sync Memory AI infrastructure into business repositories.

The sync direction is:

- project -> Obsidian -> local memory

Not:

- local memory -> project repo

unless the user explicitly wants team-facing docs generated.

## Minimal Automation Contract

A valid minimal setup has:

1. a write-back template
2. a sync script
3. a project memory destination
4. a rule to run sync after non-trivial work

Preferred setup adds:

5. a single-entry write-back + sync wrapper
