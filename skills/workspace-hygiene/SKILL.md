---
name: workspace-hygiene
description: Use when a task is about to create throwaway helper files (test probes, debug scripts, one-off verification files like test.js / *.cjs) or when deciding where temporary artifacts belong. Routes throwaway files to the central scratch area, registers must-stay-in-repo temp files with a TTL, and keeps business repositories clean over time.
---

# Workspace Hygiene

## Overview

Agents produce throwaway artifacts while working: test probes, debug scripts,
one-off verification files. Left unmanaged they accumulate in business
repositories forever. This skill defines where temporary files go and how they
get reclaimed.

The rule of thumb:

- **Short term, temp files are useful** — during the post-release verification
  window they let you re-run a check quickly when something breaks.
- **Long term, they are garbage** — recreate them when needed instead of
  keeping them around. Every temp artifact therefore carries a TTL.

## File Placement Decision

When about to create a helper file, decide in this order:

1. **Default: central scratch area.**
   Write to `runtime/scratch/<project>/<task-slug>/` in the Maestro system
   root. `set_active_task` creates this directory and returns its path as
   `scratch_dir`. Node/Python probes that only need to *call* the business
   code (HTTP probes, data checks, quick scripts) belong here.

2. **Exception: must live inside the business repo.**
   Only when the file must be discovered by the project's own tooling (a test
   runner, a bundler, a framework convention). Then:
   - create it in the business repo,
   - immediately register it with the `register_temp_file` MCP tool
     (`file_path`, `project`, `task_slug`, `reason`), default TTL 30 days,
   - never `git add` it unless the user asks to keep it permanently — a
     git-tracked file is treated as permanent and GC will refuse to touch it.

3. **Permanent tests are not temp files.** A real regression test that should
   live with the project is normal code: tracked, reviewed, committed. Do not
   register it. But it must follow the test-placement rules
   (`test-driven-development` skill): module-anchored naming, extend the
   module's existing test file instead of creating task-named siblings
   (`test-cart-fix.js` is a probe name — probes never enter test/). Suite
   health is auditable any time with the `audit_tests` MCP tool.

## TTL Semantics

- TTL default is 30 days from registration.
- When the task's state moves to `closed`, the TTL restarts from the close
  date — this covers the "recently shipped, might need to re-verify" window.
- After expiry, `gc_artifacts clean` may delete the file (dry-run by default;
  git-tracked files are always protected).

## Reclaiming Space

Run periodically (or when asked to tidy up):

```bash
bin/gc.sh scan      # report expired artifacts, read-only
bin/gc.sh archive   # gzip expired task-runs / perf-cases / task-packages / memory cases (reversible)
bin/gc.sh clean     # dry-run of scratch + temp file deletion
bin/gc.sh clean --yes  # actually delete
bin/gc.sh restore --archive-path <file.tar.gz|file.md.gz>  # undo an archive
```

Or via MCP: `gc_artifacts` with `command` = `scan` / `archive` / `clean` /
`restore`.

Archived knowledge is never lost — memory cases compress to `.md.gz` next to
their originals and `search_memory --include-archived` can still reach them.

## Response Contract

When this skill is applied, state briefly:

- where each helper file was placed (scratch vs registered-in-repo) and why
- the registered TTL for any in-repo temp file
- nothing else — placement is bookkeeping, not the task's headline
