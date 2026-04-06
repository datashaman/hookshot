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
- Creation is tied to issue number extraction from payload and presence of `load` on the command (see [How-to: worktrees](../how-to/use-worktrees-per-issue.md)).
- `issues.closed` / `issues.deleted` trigger teardown path without creating a worktree for that run.

## See also

- [Configuration](configuration.md)
