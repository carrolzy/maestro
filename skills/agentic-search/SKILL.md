---
name: agentic-search
description: Use when answering questions about live code (where a function lives, what it does now, whether a past change is still in place) or when deciding between memory RAG and live code search. Drives the multi-hop agentic loop over grep_code / glob_files / read_file_slice / repo_outline and routes between knowledge retrieval and code retrieval.
---

# Agentic Search

## Overview

Two retrieval systems, two kinds of truth:

- **Memory RAG** (`search_memory`, BM25 + embeddings over `memory/`): searches
  *write-once knowledge* — past fixes, requirements, decisions, patterns.
  Fast, semantic, and safe to trust because that corpus doesn't change after
  write-back.
- **Agentic search** (`grep_code` / `glob_files` / `read_file_slice` /
  `repo_outline`): searches *live code*. No index, no cache — every result
  comes straight from the working tree, so it can never be stale. The
  intelligence is the loop you drive, not the tools.

RAG answers "what did we know?" Agentic answers "what is true right now?"

## Routing Decision

| Question shape | Route | Why |
|---|---|---|
| "How was X fixed before?" / bug history / past optimization | `search_memory` (knowledge) | Write-once corpus, semantic recall is optimal |
| "How do we usually do X?" / business requirement / pattern | `search_memory` (knowledge) | Same |
| "Where is function X? What does it do *now*?" | agentic loop | Any index is a stale snapshot of live code |
| "Is that past change still in place?" | RAG recall → agentic verify | Memory gives direction; grep gives current fact |
| Unsure which side has signal | `search_memory` with `target="auto"` | Both cheap first-passes, labelled — dig where the signal is |

`search_memory` accepts `target="knowledge"` (default) / `"code"` /
`"auto"`, plus `repo_root` for the code side.

## The Loop (for live-code questions)

1. **Orient (wide):** `repo_outline` for structure, or `glob_files` to scope
   the file set (`src/pages/**/*.vue`). Skip if you already know the area.
2. **Anchor:** `grep_code` for identifiers, strings, or error messages.
   Prefer `fixed_string=true` for literals; add `glob` to cut noise.
3. **Read (narrow):** `read_file_slice` around each promising match — never
   whole files. Default 200 lines is usually too many; ask for what you need.
4. **Hop:** found a call site? grep the definition. Found the definition?
   grep its references. Each hop carries the previous hop's evidence.
5. **Stop when** you can cite `file:line` for the answer, or two consecutive
   hops added nothing new (then report what's known and what's missing).

**Budget:** aim for ≤ 8 tool calls per question. If the budget runs out,
report findings so far instead of silently continuing.

**Evidence contract:** every claim about code behavior cites `file:line`.
Never assert what code does from memory (yours or the RAG's) alone.

## RAG Recall → Agentic Verify (the bridge rule)

Memory cases and patterns often cite `file:line` references. Code moves;
those references rot. Whenever recalled memory is about to drive a code
change:

1. `grep_code` the cited symbol/file — confirm it still exists and still
   looks like the memory describes.
2. If it moved or changed, follow the loop to find the current location
   before acting, and note the drift in the eventual write-back so the
   memory gets corrected.

RAG provides direction and background; agentic provides current facts. Both,
in that order — never RAG alone for live code.

## The Closing of the Loop

After the task, `writeback-and-sync` records what was done as a new memory
case — today's agentic findings become tomorrow's RAG corpus. RAG owns the
past, agentic owns the present, write-back turns the present into the past.
