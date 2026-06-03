# Model Routing

## Main Model

Use for primary repo analysis, implementation, refactor, and end-to-end task handling.

## Fast Review Model

Use for quick diff review, rule compliance checks, and missing-case detection.

## Long-Context Model

Use for business-context consolidation, note organization, and write-back summaries.

## Routing Rule

- Default to the main model.
- Use the fast review model after meaningful implementation changes.
- Use the long-context model when consolidating scattered business information.
