#!/usr/bin/env python3
"""Workflow and step lifecycle state machine.

Each step and the aggregate workflow moves through a fixed set of states with
validated transitions. The state machine is the source of truth for "where are
we and what can happen next" — the engine enforces these transitions.

State diagram:

                 ┌──────────┐
                 │  pending │
                 └────┬─────┘
                      │ start
                 ┌────▼─────┐
         ┌───────│in_progress│───────┐
         │       └────┬─────┘       │
         │ fail       │ pass        │ fail
         │       ┌────▼─────┐       │
         │       │ verifying │       │
         │       └────┬─────┘       │
         │            │ pass        │
         │       ┌────▼──────┐      │
         │       │ completed  │      │
         │       └───────────┘      │
         │                          │
         │       ┌───────────┐      │
         └───────►   failed  ◄──────┘
                 └─────┬─────┘
                       │ retry
                 ┌─────▼──────┐
                 │(back to     │
                 │in_progress) │
                 └────────────┘
"""
from __future__ import annotations

from enum import Enum


class StepState(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


# Step-level allowed transitions.
_VALID_TRANSITIONS: dict[StepState, set[StepState]] = {
    StepState.PENDING: {StepState.IN_PROGRESS},
    StepState.IN_PROGRESS: {StepState.VERIFYING, StepState.COMPLETED, StepState.FAILED},
    StepState.VERIFYING: {StepState.COMPLETED, StepState.FAILED},
    StepState.COMPLETED: set(),       # terminal
    StepState.FAILED: {StepState.IN_PROGRESS},  # retry
}


# Terminal step states.
_TERMINAL_STATES: set[StepState] = {StepState.COMPLETED, StepState.FAILED}


def can_transition(current: StepState, target: StepState) -> bool:
    """Check whether a state transition is allowed."""
    return target in _VALID_TRANSITIONS.get(current, set())


def transition(current: StepState, target: StepState) -> StepState:
    """Transition to a new state, raising ValueError if invalid."""
    if not can_transition(current, target):
        raise ValueError(f"Invalid transition: {current.value} → {target.value}")
    return target


def is_terminal(state: StepState) -> bool:
    """Return True if this state will not change without a retry."""
    return state in _TERMINAL_STATES


def aggregate_state(states: list[StepState]) -> StepState:
    """Compute the aggregate workflow state from a list of step states.

    Rules (first match wins):
      - any FAILED  → FAILED
      - any PENDING → PENDING
      - any IN_PROGRESS → IN_PROGRESS
      - any VERIFYING → VERIFYING
      - all COMPLETED → COMPLETED
    """
    if not states:
        return StepState.PENDING
    if StepState.FAILED in states:
        return StepState.FAILED
    if StepState.PENDING in states:
        return StepState.PENDING
    if StepState.IN_PROGRESS in states:
        return StepState.IN_PROGRESS
    if StepState.VERIFYING in states:
        return StepState.VERIFYING
    return StepState.COMPLETED
