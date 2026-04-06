# Reference: Worktrees

```yaml
worktrees:
  path: .hookshot/worktrees
  setup: uv sync
  teardown: ''
```

## Keys

| Key | Type | Default / notes |
|-----|------|-----------------|
| `path` | string | Default `.hookshot/worktrees`. Cannot be `/` or contain `..` (validated). |
| `setup` | string or omitted | Shell command after env expansion; run once when a new worktree is created; empty → `None` (skipped). |
| `teardown` | string or omitted | Run before removing worktree on issue close; empty → `None`. |

Unknown keys → validation error.

## Behavior summary

- Worktree path: `<path>/issue-<number>` (see `hookshot.worktree`).
- Issue number comes **only** from `payload["issue"]["number"]` (`extract_issue_number`). PR-only events without an `issue` key never get a worktree path.
- Creation is tied to that extraction and presence of `load` on the command (see [How-to: worktrees](../how-to/use-worktrees-per-issue.md)).
- `issues.closed` / `issues.deleted` trigger teardown path without creating a worktree for that run.

## See also

- [Configuration](configuration.md)
