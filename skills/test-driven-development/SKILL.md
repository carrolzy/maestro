---
name: test-driven-development
description: Use when implementing any behavior change that can be covered by an automated test — new functions, bug fixes, logic changes in projects with a test setup. Enforces red → green → refactor: the failing test comes first, the implementation makes it pass, and implementation-before-test is grounds to restart.
---

# Test-Driven Development

## Overview

A test written after the implementation tests what the code *does*; a test
written before tests what the code *should do*. Only the second kind catches
you building the wrong thing.

The cycle, strictly ordered:

1. **Red** — write one failing test expressing the next small requirement.
   Run it. **Watch it fail** for the expected reason.
2. **Green** — write the minimum implementation to pass. Run it. Watch it pass.
3. **Refactor** — clean up with the test as a safety net. Run again.
4. Repeat for the next requirement.

## The Iron Rule

**"I'll write the test after" is not TDD-with-a-delay; it is not-TDD.**
If implementation exists before its test:

- for fresh work in this session: delete (or stash) the implementation,
  write the test, watch it fail, then re-apply — the failure run is what
  validates the test itself
- at minimum, if deleting is genuinely wasteful: comment out / revert the
  key behavior, confirm the new test fails against the old behavior, then
  restore. A test that has never failed proves nothing.

## Use This Skill When

- adding a function/method with definable input→output behavior
- fixing a bug (the reproduction test IS the red step — see
  `systematic-debugging`)
- changing logic in a project that has a test runner
- building Maestro tooling (unittest, zero-dep — every module has a test file)

Do not use this skill for:

- pure styling/copy changes with no testable behavior
- projects with no test infrastructure where setting one up is out of scope —
  say so explicitly, verify manually, and note the gap at write-back
- throwaway probes (those go to the scratch area per `workspace-hygiene`)

## Discipline Details

- **One behavior per test.** Small red steps localize failures. If the test
  needs three unrelated assertions, it's three tests.
- **Fail for the right reason.** A test failing on an import error is not
  red; it's broken. Read the failure output before writing implementation.
- **Minimum to green.** No speculative parameters, no "while I'm here"
  features. Extra behavior needs its own red test first.
- **Never weaken a test to pass it.** If a test seems wrong, stop and
  re-check the requirement (route to the design/plan) before touching the
  assertion.
- **Full suite before done.** The task's verification (per `writing-plans`)
  runs the relevant suite; the final task runs everything.

## Placement (bridge to workspace-hygiene)

Real regression tests are permanent code: they live in the project's test
directory, get committed, and are never registered as temp files. One-off
probes used to explore behavior are scratch: `runtime/scratch/<project>/
<task-slug>/`. When a probe turns out to encode a real regression, promote it
into the test suite properly (naming, assertions, committed) — don't leave it
half-alive in the repo root.

## Test-File Placement Rules (suite bloat prevention)

Test directories grow without bound when every task spawns a new file. Rules:

1. **Extend before creating.** Before adding a test file, `grep_code` the
   test directory for the module's existing test file — if
   `test_cart.py` / `cart.spec.ts` exists, add your cases THERE. Creating a
   second test file for a module already covered requires a stated reason.
2. **Module-anchored naming only.** A test file is named after the module it
   covers (`test_cart.py` ↔ `cart.py`) — never after the task that produced
   it. Names containing `-fix`, `-final`, `-v2`, `-debug`, dates, or bare
   number suffixes are probe names: those files belong in scratch, not test/.
3. **Never "tidy" a probe into test/.** Moving a one-off verification script
   into the test directory and committing it disguises garbage as a
   regression suite — it then evades artifact GC forever (git-tracked files
   are protected by design).

Periodic cleanup: `audit_tests` (MCP) reports orphaned / task-named / stale /
duplicate-coverage test files with suggested actions — report only, human
confirms.

## Response Contract

When reporting a TDD task complete, show the evidence trail: the failing run
(red), the passing run (green), and the final suite result. "Tests pass" with
no red run on record means the cycle was not followed — say so honestly
rather than claiming TDD.
