---
name: brainstorming
description: Use before writing any code for a non-trivial feature, refactor, or design decision — when requirements are still rough, when multiple approaches exist, or when the user describes an idea rather than a precise change. Refines the requirement through questions, explores alternatives, and locks a design the user has confirmed section by section.
---

# Brainstorming

## Overview

Code written against a rough idea gets rewritten when the idea sharpens. This
skill front-loads that sharpening: question the requirement, explore
alternatives, and get the design confirmed **before** implementation starts.

It is a pre-implementation design skill. It produces a confirmed design
document; it never produces code.

## Use This Skill When

- a new feature or capability is requested and the shape is not yet exact
- a refactor has more than one reasonable target architecture
- the user describes an idea, a pain point, or a "what if" — not a precise diff
- a task package's requirement line leaves open questions you would otherwise
  guess at

Do not use this skill for:

- trivial changes with an obvious single implementation
- bugfixes (use `systematic-debugging` — bugs need diagnosis, not design)
- work where the user has already given a precise, complete specification

## Required Workflow

### 1. Ground in context first

Run `memory-read-first` for the project before asking anything — prior cases,
patterns, and the business card answer many questions and make the remaining
ones sharper. For live-code questions that shape the design ("how is X
structured today?"), use the `agentic-search` loop and cite `file:line`.

### 2. Refine through questions

Ask questions **one at a time** — never a wall of questions. Prefer options
over open-ended asks: propose 2-4 concrete choices with trade-offs and a
recommendation, so answering costs the user seconds.

Keep asking until you can state, in one paragraph, what will be built and how
you will know it works. Cover at minimum:

- purpose: what user-visible outcome this serves
- scope boundary: what is explicitly NOT included
- constraints: performance, compatibility, existing conventions
- verification: how the result will be checked

### 3. Explore alternatives honestly

Before settling, present at least two approaches when they genuinely exist
(e.g. MVP-first vs robustness-first, extend-existing vs new-module). For each:
one-line description, main trade-off, your recommendation and why. If only one
sensible approach exists, say so — do not manufacture fake alternatives.

### 4. Present the design in sections

Deliver the design incrementally — one section at a time, each ending with an
explicit confirmation ask ("does this match your intent?"). Sections:

1. Goal + non-goals
2. Approach chosen and why (alternatives noted)
3. Changes by file/module (what, not full code)
4. Verification plan
5. Risks and open questions

Do not proceed to the next section on silence; wait for confirmation. Revise
the section the user pushes back on before moving forward.

### 5. Save the design document

Write the confirmed design to
`docs/superpowers/specs/<date>-<slug>-design.md` (for Maestro-system work) or
the project's equivalent docs area. The document is the input contract for
`writing-plans` — it must be complete enough that planning needs no further
user questions.

## Response Contract

At the end, state:

- the design document path
- the one-paragraph summary of what will be built
- the next step: run `writing-plans` against this design

## Failure Rules

- If the user cannot answer a scoping question, park it as an explicit open
  question in the design — do not silently pick an answer.
- If exploration reveals the request is trivial after all, say so and skip to
  implementation — do not force ceremony onto a one-line change.
- Never start implementing "just the obvious part" while the design is
  unconfirmed. The obvious part is where rewrites start.
