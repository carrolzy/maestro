#!/usr/bin/env python3
"""Deterministic workflow engine.

Accepts a workflow definition (a step DAG), resolves dependencies, and executes
each step by calling the canonical `server.invoke(tool, args)`. Steps with
satisfied dependencies run in parallel. The engine tracks per-step state,
handles retries, and returns a structured result.

The engine is model-agnostic — it calls existing Maestro tool functions, never
an LLM. The LLM (or human) defines the steps; the engine enforces order,
parallelism, and lifecycle.
"""
from __future__ import annotations

import json
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any
from pathlib import Path

from update_task_run_state import update_task_run_state
from workflow_state import StepState, aggregate_state, is_terminal, transition

JsonDict = dict[str, Any]

# Sentinel for steps that were skipped because a dependency failed.
_SKIPPED = object()

# Built-in orchestration verbs (not in TOOL_SPECS, handled by the engine).
_BUILTIN_TOOLS = {"fan_out"}


class WorkflowEngine:
    """Execute a workflow definition deterministically."""

    def __init__(self, server: Any) -> None:
        """`server` must have an `invoke(tool_name, arguments) -> dict` method."""
        self._server = server
        self._max_workers = 8  # cap parallel tool calls

    def run(self, definition: JsonDict) -> JsonDict:
        """Execute a workflow definition and return the result.

        Result shape:
          {"project": ..., "task_slug": ..., "aggregate_state": ...,
           "steps": [{"id": ..., "state": ..., "output": ..., "elapsed_ms": ...}, ...],
           "total_elapsed_ms": ...}
        """
        steps = definition.get("steps", [])
        project = definition.get("project", "")
        task_slug = definition.get("task_slug", "")

        _validate_definition(steps)
        runtime_root = self._runtime_root(project, task_slug)
        if runtime_root is not None:
            update_task_run_state(
                runtime_root=runtime_root,
                project=project,
                task_slug=task_slug,
                state="in_progress",
            )

        # Per-step tracking.
        step_states: dict[str, StepState] = {s["id"]: StepState.PENDING for s in steps}
        step_outputs: dict[str, Any] = {s["id"]: None for s in steps}
        step_elapsed: dict[str, float] = {s["id"]: 0.0 for s in steps}
        step_attempts: dict[str, int] = {s["id"]: 0 for s in steps}
        step_map: dict[str, dict] = {s["id"]: s for s in steps}

        t0 = time.monotonic()

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            pending_futures: dict[Future, str] = {}
            # Track which steps were submitted this tick to avoid double-submit.
            submitted: set[str] = set()

            while True:
                # Find runnable steps: all deps COMPLETED, step not yet running/terminal.
                runnable = []
                for s in steps:
                    sid = s["id"]
                    if sid in submitted:
                        continue
                    if is_terminal(step_states[sid]):
                        continue
                    deps = s.get("depends_on", [])
                    if not deps:
                        runnable.append(s)
                        continue
                    # Blocked by a failed dependency?
                    if any(step_states[d] == StepState.FAILED for d in deps):
                        step_states[sid] = StepState.FAILED
                        step_outputs[sid] = {"error": "dependency failed"}
                        continue
                    # All deps completed?
                    if all(step_states[d] == StepState.COMPLETED for d in deps):
                        runnable.append(s)

                if not runnable and not pending_futures:
                    break  # all done or blocked

                # Submit runnable steps.
                for s in runnable:
                    sid = s["id"]
                    step_states[sid] = transition(step_states[sid], StepState.IN_PROGRESS)
                    step_attempts[sid] += 1
                    submitted.add(sid)
                    fut = pool.submit(self._execute_step, s)
                    pending_futures[fut] = sid

                if not pending_futures:
                    # Nothing running and nothing new — must be all terminal.
                    continue

                # Wait for at least one future to complete, then re-evaluate the DAG.
                # Use as_completed to drain as they finish within one tick.
                done_futures: set[Future] = set()
                for fut in as_completed(pending_futures):
                    done_futures.add(fut)
                    sid = pending_futures[fut]
                    step_states[sid], step_outputs[sid], step_elapsed[sid] = fut.result()
                    # Only process one at a time to re-check the DAG for newly
                    # unblocked steps. (as_completed yields in completion order.)
                    break

                # Remove the done future.
                for fut in done_futures:
                    del pending_futures[fut]

                # If a step failed and has retries left, retry it.
                for s in steps:
                    sid = s["id"]
                    if step_states[sid] == StepState.FAILED and _should_retry(s, step_attempts[sid]):
                        step_states[sid] = transition(step_states[sid], StepState.IN_PROGRESS)
                        submitted.discard(sid)  # allow re-submit next tick
                        # Submit it immediately so the runnable loop above
                        # doesn't try to transition IN_PROGRESS → IN_PROGRESS.
                        step_attempts[sid] += 1
                        fut = pool.submit(self._execute_step, s)
                        pending_futures[fut] = sid
                        submitted.add(sid)

        total_elapsed_ms = round((time.monotonic() - t0) * 1000)

        step_results = []
        for s in steps:
            sid = s["id"]
            step_results.append({
                "id": sid,
                "state": step_states[sid].value,
                "output": step_outputs[sid],
                "elapsed_ms": round(step_elapsed[sid] * 1000),
                "attempts": step_attempts[sid],
            })

        result = {
            "project": project,
            "task_slug": task_slug,
            "aggregate_state": aggregate_state(list(step_states.values())).value,
            "steps": step_results,
            "total_elapsed_ms": total_elapsed_ms,
        }
        if runtime_root is not None:
            record_path = runtime_root / "task-runs" / project / task_slug / "workflow.json"
            record_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            update_task_run_state(
                runtime_root=runtime_root,
                project=project,
                task_slug=task_slug,
                state=result["aggregate_state"],
            )
        return result

    def _runtime_root(self, project: object, task_slug: object) -> Path | None:
        if not isinstance(project, str) or not project:
            return None
        if not isinstance(task_slug, str) or not task_slug:
            return None
        system_root = getattr(self._server, "system_root", None)
        return Path(system_root) / "runtime" if system_root is not None else None

    def _execute_step(self, step: dict) -> tuple[StepState, Any, float]:
        """Execute one step: call the tool, handle verification, measure time."""
        t0 = time.monotonic()
        sid = step["id"]
        tool = step.get("tool", "")

        try:
            # Built-in verbs
            if tool == "fan_out":
                output = self._run_fan_out(step)
            else:
                output = self._server.invoke(tool, step.get("args", {}))

            elapsed = time.monotonic() - t0

            # Optional verification gate
            if "verify" in step:
                state = transition(StepState.IN_PROGRESS, StepState.VERIFYING)
                ok = self._run_verification(step, output)
                if ok:
                    state = transition(state, StepState.COMPLETED)
                else:
                    state = transition(state, StepState.FAILED)
                    if not isinstance(output, dict):
                        output = {"value": output}
                    output["verification_failed"] = True
                return state, output, elapsed

            return StepState.COMPLETED, output, elapsed
        except Exception as exc:
            elapsed = time.monotonic() - t0
            return StepState.FAILED, {"error": str(exc)}, elapsed

    def _run_fan_out(self, step: dict) -> list[JsonDict]:
        """Built-in fan_out: run items in parallel, collect results."""
        items = step.get("args", {}).get("items", [])
        if not items:
            return []

        results: list[JsonDict | None] = [None] * len(items)

        def _run_one(index: int, item: dict) -> tuple[int, JsonDict]:
            return index, self._server.invoke(item["tool"], item.get("args", {}))

        with ThreadPoolExecutor(max_workers=min(len(items), self._max_workers)) as pool:
            futures = {pool.submit(_run_one, i, item): i for i, item in enumerate(items)}
            for fut in as_completed(futures):
                idx, result = fut.result()
                results[idx] = result

        return results  # type: ignore[return-value]

    def _run_verification(self, step: dict, _output: Any) -> bool:
        """Run a verification gate. Returns True if the step passes."""
        verify = step.get("verify", {})
        condition = verify.get("condition", "always_pass")

        if condition == "always_pass":
            return True
        if condition == "always_fail":
            return False
        if condition == "output_not_empty":
            return bool(_output)
        if condition == "no_error":
            if isinstance(_output, dict):
                return "error" not in _output
            return True
        # Unknown condition: warn but pass (don't block on a bad gate definition).
        return True


# ── helpers ───────────────────────────────────────────────────────────


def _validate_definition(steps: list[dict]) -> None:
    ids = [s.get("id") for s in steps]
    seen: set[str] = set()
    for sid in ids:
        if not isinstance(sid, str) or not sid:
            raise ValueError("every step must have a non-empty string id")
        if sid in seen:
            raise ValueError(f"duplicate step id: {sid!r}")
        seen.add(sid)

    # Dependency references must exist.
    for s in steps:
        for dep in s.get("depends_on", []):
            if dep not in seen:
                raise ValueError(f"step {s['id']!r} depends on unknown step {dep!r}")

    # Circular dependency check (topological sort).
    _topological_order(steps)


def _topological_order(steps: list[dict]) -> list[str]:
    """Return a valid topological order, or raise on cycle."""
    in_degree: dict[str, int] = {s["id"]: 0 for s in steps}
    adj: dict[str, list[str]] = {s["id"]: [] for s in steps}
    for s in steps:
        for dep in s.get("depends_on", []):
            adj[dep].append(s["id"])
            in_degree[s["id"]] += 1

    queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
    order: list[str] = []
    while queue:
        sid = queue.popleft()
        order.append(sid)
        for neighbor in adj[sid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(steps):
        raise ValueError("circular dependency detected in workflow steps")
    return order


def _should_retry(step: dict, attempts: int) -> bool:
    retry = step.get("retry")
    if not isinstance(retry, dict):
        return False
    max_attempts = retry.get("max_attempts", 1)
    return attempts < max_attempts
