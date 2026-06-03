# Projects

Create one folder per concrete project.
Each project folder should contain:

- `project-override.md`
- `business-context.md`
- `task-context.md`

Only put project-specific deltas here.
Do not duplicate project-type template content unless the project differs from the template.

To register a new project shell with the canonical files, use:

```bash
bin/register-project.sh --project <slug> --summary "<one sentence>" [--project-type <type>]
```
