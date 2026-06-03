# Obsidian Write-Back

## Default Path

`project-notes/codex-auto/<topic>/<YYYY-MM-DD>-<slug>.md`

## Minimum Sections

- Request
- Context Used
- Implementation
- Verification
- Risks / Follow-up
- File References

## Rule

Only write back reusable decisions, debugging paths, or workflow improvements.
Do not write secrets or irrelevant terminal noise.

## Preferred Local Entry

For non-trivial project work, prefer the local wrapper that writes the note and syncs project memory in one step:

```bash
tooling/writeback_and_sync_memory.sh <project> <note-path> <source-file>
```

or:

```bash
python3 tooling/writeback_and_sync_memory.py \
  --vault-root /Users/apple/Documents/my-knowledge-base \
  --project <project> \
  --note-path <note-path> \
  --source-file <source-file>
```
