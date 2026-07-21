---
name: systematic-debugging
description: Use when investigating any bug, error, unexpected behavior, or "it worked before" report — before attempting a fix. Enforces a four-phase discipline (reproduce → locate → understand → fix with a regression test) and forbids fixing code whose failure mechanism is not yet understood.
---

# Systematic Debugging

## Overview

Guessed fixes have three outcomes: they miss, they mask, or they accidentally
work and leave a landmine. This skill forbids all three by enforcing one iron
rule:

**Do not change code you have not understood. "Understood" means you can
state the failure mechanism in one sentence and predict which change makes
the symptom disappear — before making it.**

## The Four Phases (strictly in order)

### Phase 1 — Reproduce

- Get a reliable reproduction: exact steps, input, environment, error output.
- If it can be captured as a failing automated test, write that test NOW —
  it becomes the red step of the eventual fix (see
  `test-driven-development`). A one-off reproduction script goes to the
  scratch area (`workspace-hygiene`).
- Can't reproduce → stop fixing; gather more information (logs, versions,
  data state). A fix for an unreproduced bug is a guess by definition.

### Phase 2 — Locate

- Check memory first: `search_memory` for prior cases of the same symptom in
  this project — recurring bugs usually share a root cause. Verify any
  recalled `file:line` against live code (`agentic-search` bridge rule).
- Trace with live evidence, not recollection: `grep_code` the error message /
  symptom keywords, follow the call chain hop by hop, `read_file_slice`
  around each candidate. Cite `file:line` for every claim.
- Narrow by bisection where cheap: `git log` recent changes to the involved
  files ("worked before" almost always means "something changed"), binary-
  search inputs, isolate layers.

### Phase 3 — Understand

- State the failure mechanism in one sentence:
  "X happens because Y does Z when W." If the sentence contains "probably"
  or "somehow", you are still in Phase 2.
- Explain why the code was written the way it was before calling it wrong —
  the "bug" is sometimes a constraint you haven't seen yet
  (check `project-override.md`, playbook risk flags, prior cases).
- Predict: which minimal change eliminates the symptom, and what else that
  change could affect (blast radius).

### Phase 4 — Fix

- Red: the Phase-1 reproduction test fails.
- Green: apply the minimal fix predicted in Phase 3. The test passes.
- Run the surrounding suite — a fix that breaks neighbors is not done.
- If the first predicted fix does NOT work: that is new evidence that the
  understanding was wrong. **Return to Phase 2.** Do not stack a second
  guess on top of a failed one — serial guessing is how codebases rot.

## Anti-Patterns (all forbidden)

- Shotgun debugging: changing several things at once, keeping whatever
  "works". You learn nothing and ship side effects.
- Symptom-patching: adding a null-check / try-catch / retry where the error
  *appears* instead of where it *originates*, without stating the mechanism.
- "It works now" with no explanation of why it was broken — the bug is not
  fixed, it is dormant.
- Deleting failing tests or loosening assertions to make red go away.

## Escalation Rule

After 3 failed fix predictions, or 2 hours without a mechanism sentence:
stop, write down everything known/ruled out (in the task's scratch area or
checkpoint), and either hand off (`handoff_task` with findings) or take the
question to the user. Documented dead-ends are progress; undocumented
thrashing is not.

## Response Contract

A debugging report states: the reproduction, the mechanism sentence with
`file:line` evidence, the fix and its blast-radius check, and the regression
test now guarding it. At write-back, record the case so the next occurrence
starts from memory instead of from zero.
