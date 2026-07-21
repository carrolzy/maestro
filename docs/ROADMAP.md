# Maestro Roadmap

Maestro began as a personal set of reusable AI execution assets (memory,
project-type templates, rules, skills, task packages). The goal is to evolve it
into an **agent orchestration product**: a model-agnostic system that any LLM
can plug into and use to serve arbitrary business projects.

The published repository is the **framework baseline**. Real business projects,
their memory, and their runtime artifacts stay local and are never committed.

## North Star

A business can onboard by describing itself once (a business card + a playbook),
and any connected model can then plan, execute, verify, and write back work
against that business — with reusable memory and standing rules carried across
tasks.

## Phases

### Phase 0 — Reusable asset library (done / baseline)
- Layered memory (`memory/{projects,patterns,rules}`)
- Project-type templates (`project-types/`) and copy-ready templates (`templates/`)
- Skills for intake, registration, memory-first reads, verification, and write-back
- Task-package builder and task-run lifecycle state
- Pluggable, business-free guidance via per-project `playbook.json`

### Phase 1 — MCP tool layer (in progress)
- `tooling/ai_efficiency_mcp_server.py` exposes the core operations as MCP tools
  (`search_memory`, `build_task_package`, `register_project`,
  `update_task_run_state`, `writeback_and_sync_memory`, `doctor_local_skills`)
- ✅ Every tool declares `inputSchema` + `outputSchema` with per-field
  descriptions and a title; `initialize` negotiates `protocolVersion`; `ping`
  is supported
- ✅ Zero-dependency conformance suite validates handshake, discovery, and that
  each tool's live output matches its declared schema
  (`tooling/tests/test_mcp_conformance.py`, `tooling/jsonschema_mini.py`)
- ✅ `bin/context-pack.sh` emits a model-agnostic context pack for raw-API models

### Phase 2 — Model-agnostic adapter layer (in progress)
- ✅ Single canonical tool registry (`tooling/tool_registry.py`, `TOOL_SPECS`) is
  the source of truth consumed by both the MCP server and the adapters; the
  server gained `invoke()` for unwrapped canonical dispatch
- ✅ Thin per-provider adapters (`tooling/adapters/`) translate the same six
  tools into each provider's native function-calling format and parse tool-calls
  back to a canonical `(name, arguments)` — covering **OpenAI, DeepSeek,
  Anthropic, Gemini** (Gemini includes an OpenAPI-subset schema sanitizer)
- ✅ `bin/provider-tools.sh` lists native declarations and dispatches calls;
  `tooling/tests/test_adapters.py` checks declaration coverage and round-trip
  dispatch validated against each tool's `outputSchema`
- No business logic in adapters, no SDK/network deps (pure translation)
- Next: standardize multi-turn tool-result framing per provider (toward Phase 4)

### Phase 3 — Pluggable business onboarding ✅
- ✅ `tooling/playbook_schema.py`: formal JSON Schema for `playbook.json` with
  `validate_playbook()` / `load_and_validate_playbook()` using `jsonschema_mini`
- ✅ `tooling/project_types.py`: scans `project-types/` directories, returns
  typed metadata (description, rules, pitfalls); CLI `--list` and MCP tool
- ✅ `tooling/business_card.py`: structured `business-card.json` with schema
  validation, starter generation, and `card_to_markdown()` renderer
- ✅ `tooling/validate_project.py`: checks canonical files, playbook, business
  card, and project-type membership — returns a machine-readable report
- ✅ `tooling/onboard_project.py`: guided one-command onboarding — registers,
  generates playbook + business card, validates, prints readiness report
- ✅ 2 new MCP tools (`validate_project`, `list_project_types`) with full
  inputSchema/outputSchema; conformance-tested
- A business is fully described by tracked, generic-shaped config: business
  card + `playbook.json` + project-type selection. No business specifics in
  core code.
- Next: orchestration runtime (Phase 4)

### Phase 4 — Orchestration runtime ✅
- ✅ `tooling/workflow_state.py`: proper lifecycle state machine
  (pending→in_progress→verifying→completed|failed; retry loop) with validated
  transitions and aggregate state computation
- ✅ `tooling/workflow_engine.py`: deterministic DAG executor — resolves
  dependencies, runs independent steps in parallel (concurrent.futures),
  dispatches through `server.invoke()`, blocks dependents on failure, retries
  with configurable max_attempts
- ✅ Built-in orchestration verbs: `fan_out` (parallel tool array), `gate_check`
  (verification conditions: always_pass, always_fail, no_error, output_not_empty)
- ✅ 2 new MCP tools (`run_workflow`, `get_workflow_status`) with full
  inputSchema/outputSchema; conformance-tested
- ✅ 130 tests all green; preflight clean
- Multi-step pipelines run deterministically — the engine is infrastructure,
  the LLM supplies the intelligence. Next: product surface (Phase 5)

### Phase 5 — Product surface ✅
- ✅ `tooling/api_server.py`: stdlib `http.server` JSON REST API (zero new
  dependencies) wrapping `AiEfficiencyMcpServer` — endpoints for projects
  CRUD, tools list+invoke, workflow run, memory search, project-types
- ✅ `tooling/ui/dashboard.html`: single-page visual dashboard — four tabs
  (Projects with onboard modal, Tools with dynamic form+invoke, Workflows
  with JSON editor+presets+step results, Memory with search+browse). Dark
  theme, vanilla JS+CSS, no build step, no npm.
- ✅ `bin/dashboard.sh`: one-command launcher — starts the API server and
  opens the browser. Zero-memory-cost visual control.
- ✅ 17 API server tests (HTTP-level, real server in thread) + 147 total
  tests all green; preflight clean
- Maestro 1.0 complete: from CLI toolbox to visual autopilot. Every tool,
  project, workflow, and memory search is clickable, browsable, and
  live-validated.

### Phase 6 — Agent-to-Agent Handoff (A2A) ✅
- ✅ `tooling/checkpoint.py`: structured `Checkpoint` dataclass —
  agent/step/state/summary/output/files_modified/next_hint/timestamp.
  `save_checkpoint()`, `load_latest_checkpoint()`, `list_checkpoints()`,
  `build_resume_context()` with self-contained markdown resume pack.
- ✅ `update_task_run_state` enhanced with optional `agent` parameter.
  Every state transition records which agent made it. Backward-compatible.
- ✅ 2 new MCP tools: `resume_task` (build full resume context from
  checkpoints) and `handoff_task` (explicit agent-to-agent handoff with
  checkpoint + state transition to `handed_off`)
- ✅ `resume_context_pack` is a self-contained markdown string —
  injectable directly into any agent's prompt with no tool calls needed.
  Contains: original requirement, agent history, completed steps with
  summaries, files modified, next-step hint, latest output, and explicit
  instructions for the resuming agent.
- ✅ 162 tests all green; preflight clean
- Codex crashes → Claude opens → `resume_task("my-app", "cart-fix")` →
  gets full context → continues exactly where Codex left off.
  No dead loops, no memory corruption, no semantic drift.

### P0 — Forced checkpoints via PostToolUse hooks ✅
- ✅ `tooling/active_task.py`: active-task pointer (cross-process fcntl lock)
  bridges "which file was edited" → "which task it belongs to". Runtime root is
  anchored to the Maestro repo from the script's own location, so edits made
  from inside a *business project* still record to the central store.
- ✅ `tooling/hooks/checkpoint_hook.py`: runtime-agnostic PostToolUse hook.
  **Claude**: matches `Edit`/`Write`, path from `tool_input.file_path`.
  **Codex**: codex-cli 0.135 only fires PostToolUse reliably for the shell/Bash
  tool — `apply_patch`/MCP edits don't fire yet (openai/codex#16732) — so on
  Codex the hook matches `shell` and parses the command text for the written
  file (apply_patch heredoc body, `> file` redirection, `tee`, `sed -i`). A
  shell command with no write target records nothing. Always exits 0 — never
  blocks an edit. `AI_EFF_HOOK_DEBUG=1` dumps raw payloads.
- ✅ Session-merge: consecutive same-session edits collapse into one `auto-edit`
  checkpoint (sealed once an explicit checkpoint lands after it) — no explosion.
- ✅ `set_active_task` MCP tool (13 tools now); `build_task_package` auto-sets
  the pointer. Both `bin/setup-claude.sh` (JSON, `command` as array) and
  `bin/setup-codex.sh` (TOML, `command` as a single shell string, matcher
  `shell|Bash|apply_patch|Edit|Write`) register the hook automatically. Codex
  requires a one-time `/hooks` trust of the new hook before it fires; editing
  the hook changes its hash and re-triggers the trust prompt.
- ✅ 27 checkpoint/hook tests (incl. Codex shell+apply_patch heredoc, `> / tee /
  sed -i` redirections, and no-write commands that must NOT record); 189 tests
  total, all green; generated Codex inline-hook TOML validated.
- Checkpoints are now **forced**, not left to model discretion — the handoff
  chain never breaks even if an agent forgets to checkpoint. Works **both
  directions**: Codex↔Claude.
- ⚠️  **Codex limitation** (0.135–0.137): PostToolUse hooks parse and trust but
  the engine does not spawn them at edit time (upstream regressions #16246 /
  #16732 / #21639). The hook config is kept ready for the day Codex fires it.
- ✅ **`snapshot_task` MCP tool** (14 tools now): runtime-independent git-based
  checkpoint. Calls `git status --porcelain`, records every changed file as a
  session-merge checkpoint. Works on Codex, Claude, or any agent.
- ✅ **Auto-snapshot embedded in `set_active_task` and `handoff_task`**: zero
  manual steps. Switching active tasks snapshots the previous task's changes;
  handing off snapshots the current task's changes. Codex just works — start a
  task, edit files, hand off (or switch tasks), and all changes are captured.

### P0 — Semantic memory search ✅
- ✅ `tooling/text_rank.py`: pure-Python Okapi **BM25** ranker (k1=1.5, b=0.75).
  Replaces the old token-count scoring (which gave every term equal weight and
  ignored document length). BM25 adds term-frequency saturation, IDF (rare
  terms carry more signal), and length normalization. On real memory data the
  relevant doc now scores 6000×+ above an irrelevant one (token-count gave both
  a hit).
- ✅ **CJK bigram tokenization**: Chinese has no word spaces, so "登录按钮" used
  to be one opaque token that only matched verbatim. The tokenizer now expands
  CJK runs into overlapping bigrams + unigrams, so a query "登录" matches a doc
  containing "登录按钮" — critical for the Chinese-heavy memory corpus.
- ✅ `tooling/embedding_index.py`: optional semantic layer. Stores doc vectors
  in `memory/.embedding_cache.json`; cosine similarity via pure-Python math (no
  numpy). `search_memory` blends BM25 (0.7) + embedding cosine (0.3) when an
  index + embedding API key exist; degrades cleanly to BM25-only offline.
- ✅ `tooling/build_embedding_index.py`: stdlib-only CLI to build the index from
  any OpenAI-compatible `/v1/embeddings` endpoint (`AI_EFF_EMBED_*` env vars).
- ✅ `search_memory` and `task_package_builder` both route through the shared
  BM25 engine — no more duplicated `any(token in text)` matching. 29 new tests
  (BM25 ranking, CJK matching, cosine, index persistence); 221 total green.

### P0 — Artifact lifecycle & workspace hygiene ✅
- Pain: throwaway helper files (test.js / *.cjs probes) accumulated in
  business repos, and runtime artifacts grew without bound (one perf trace was
  62 MB). Both are solved industry-wide (session scratchpads, memory paging) —
  Maestro now has its own lifecycle layer.
- ✅ `tooling/artifact_gc.py`: retention engine over `base/retention.json` —
  `scan` (read-only report), `archive` (gzip task-runs / task-packages /
  perf-cases / memory-cases into `runtime/archive/`, reversible via
  `restore`), `clean` (delete expired scratch + registered temp files;
  dry-run by default, git-tracked files always protected). Memory patterns
  and rules are permanent and never governed. `bin/gc.sh` wraps it.
- ✅ `tooling/temp_registry.py`: TTL registry for helper files that must live
  inside a business repo. TTL restarts when the task closes — covering the
  post-release "might need to re-verify" window — then the file is garbage.
- ✅ Central scratch area `runtime/scratch/<project>/<task-slug>/`, provisioned
  by `set_active_task` (returns `scratch_dir`); throwaway probes belong there,
  not in the business repo.
- ✅ 2 new MCP tools (16 total): `gc_artifacts`, `register_temp_file`.
  `search_memory` gains `include_archived` (archived `.md.gz` cases are
  skipped by default, still reachable on demand).
- ✅ New `workspace-hygiene` skill; `verification-before-close` now blocks
  `closed` while unregistered throwaway files remain in the business repo.
- ✅ 25 new tests (GC scan/archive/restore/clean, registry TTL, archived-case
  search); 249 total green. First real run archived 62 MB of perf traces down
  to 4.2 MB.

### P0 — Agentic search & retrieval routing ✅
- Insight (industry-validated by Claude Code): live code must never be served
  from a static index — code changes with every commit, so any index is a
  stale snapshot. Instead: fast live-search primitives + a model-driven
  multi-hop loop. RAG stays for what it's best at: the write-once memory
  corpus (cases, patterns, rules).
- ✅ `tooling/code_search.py`: four zero-dep primitives, all taking a
  `repo_root` so any MCP client (Codex especially) can search any registered
  business repo through one protocol —
  `grep_code` (ripgrep when present, pure-Python fallback; file:line +
  context), `glob_files` (newest first), `read_file_slice` (bounded line
  ranges, no whole-file dumps), `repo_outline` (live directory tree /
  regex-ctags symbols; computed per call, never persisted — the freshness
  guarantee).
- ✅ `search_memory` becomes the unified retrieval entry point with `target`:
  `knowledge` (default, BM25+embedding RAG over memory/ — unchanged),
  `code` (live grep seed + explicit instruction to continue agentically),
  `auto` (both cheap first-passes, labelled by source).
- ✅ New `agentic-search` skill: routing table (history/requirements → RAG;
  live code → agentic loop), loop discipline (orient → anchor → read → hop;
  ≤8 tool calls; stop on file:line evidence or two dry hops), and the bridge
  rule — **RAG recall → agentic verify**: recalled `file:line` references
  must be confirmed against the working tree before driving changes, and
  drift gets corrected at write-back.
- ✅ `memory-read-first` gains the recall-verification step; the retrieval
  loop closes: RAG owns the past, agentic owns the present, write-back turns
  the present into the past.
- ✅ 4 new MCP tools (20 total); 24 new tests (rg + pure-Python engines, CJK
  content, routing targets); 272 total green.

### P1 — Methodology skill layer ✅
- Gap identified against Superpowers (the 2026 benchmark for agentic dev
  methodology): Maestro's skills disciplined task *entry* (intake, memory
  read) and *exit* (verification, write-back) but left the implementation
  process in between unconstrained. Four new markdown-only skills close it:
- ✅ `brainstorming`: pre-code design refinement — one-question-at-a-time
  with options, honest alternatives, section-by-section confirmation; saves
  a design doc to `docs/superpowers/specs/`. Grounded in memory-read-first
  and agentic-search before asking.
- ✅ `writing-plans`: decomposes a confirmed design into small independently
  verifiable tasks (exact files + change description + verification command
  + dependencies); reality-checks the design against live code first; plan
  doc in `docs/superpowers/plans/`; execution contract = verify each task
  before the next.
- ✅ `test-driven-development`: red → green → refactor, strictly ordered;
  implementation-before-test is grounds to restart (a test that never failed
  proves nothing); permanent tests → suite, probes → scratch
  (workspace-hygiene bridge).
- ✅ `systematic-debugging`: reproduce → locate → understand → fix; iron rule
  "do not change code whose failure mechanism you cannot state in one
  sentence"; failed prediction returns to locate (never stack guesses);
  escalate after 3 misses with documented findings. Locate phase runs on
  memory recall + agentic-search live evidence.
- ✅ Full execution order documented in `skills/README.md` (lifecycle skills
  vs methodology skills); each methodology skill declares explicit skip
  conditions so trivial work stays ceremony-free.
- Zero code changes — pure skill layer. The complete loop now reads:
  intake → memory → brainstorm → plan → (TDD / debug / search) → verify →
  write back.

## Design Principles

- **Business stays out of core.** Generic engine + per-project config only.
- **Memory before work.** Read prior context before starting; write back after.
- **Verify before close.** No task is closed without evidence.
- **Local-first boundaries.** Real project data never leaves the user's machine
  unless they explicitly choose to.
