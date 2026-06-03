# Memory Boundary

## Principle

Memory AI infrastructure belongs to the local AI efficiency system, not to business project repositories.

## Keep Local Only

The following should live only under `/Users/apple/Downloads/workspace/ai-efficiency-system/`:

- memory directory structure
- sync scripts
- reusable patterns
- reusable rules
- personal operating conventions
- project memory mirrors
- retrieval flow docs

## Do Not Put In Project Repos By Default

Do not add these to a business repository unless there is explicit team value and explicit user intent:

- personal memory automation scripts
- personal checklists and routing rules
- project memory mirrors used only by the local agent workflow
- cross-project reusable patterns owned by the local efficiency system

## Allowed In Project Repos

Only put documentation into the business project when it is one of:

- required for teammates to execute or maintain the project
- required for project build or runtime
- part of official project architecture or troubleshooting docs
- intentionally shared team knowledge

## Default Direction

- project work produces Obsidian write-back notes
- Obsidian notes sync into local AI efficiency system memory
- only team-relevant material may be promoted back into the project repo

## Smell Test

If removing the file would only hurt your personal agent workflow, it belongs locally.

If removing the file would hurt teammates or project maintainability, it may belong in the project repo.
