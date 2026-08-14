<!-- maestro:managed:start -->
# Maestro Project Workflow

This repository is registered with the local Maestro agents system.

- Project slug: `{{PROJECT_SLUG}}`
- Maestro system root: `{{MAESTRO_ROOT}}`

For non-trivial feature, bug-fix, refactor, debugging, or investigation work:

1. Use `project-intake` with the registered project slug to create a task package before editing code.
2. Use `memory-read-first` to read project context and relevant project memory before implementation.
3. Create a Change Spec through the Maestro MCP tools, with explicit allowed files, behavior changes, non-goals, acceptance criteria, and verification.
4. Do not edit business code until `approve_change_spec` records a named approver and source reference, then `spec_gate` passes. A request to change module A does not authorize changing module B, adding a fallback, or refactoring adjacent code.
5. Record progress checkpoints after meaningful edits.
6. Use `verification-before-close` and run focused verification before declaring completion.
7. Use `writeback-and-sync` to write the completed result back to Obsidian and project memory.

For simple questions or harmless one-line edits, do not create a task package unless the user requests durable tracking.

Do not replace this managed block manually. Repository-specific rules may be added outside the markers.
<!-- maestro:managed:end -->
