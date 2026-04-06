# How to use worktrees per issue

**Goal:** Run hook commands in an isolated git worktree keyed by issue number (e.g. `.hookshot/worktrees/issue-42`).

## When Hookshot uses a worktree

Worktrees apply only when **all** of the following hold:

1. Top-level `worktrees` is configured.
2. The webhook payload is **issue-shaped**: it includes a top-level `issue` object with `number` (for example `issue_comment` on an issue, or payloads that nest the issue under `issue`). Payloads that only carry pull-request context under `pull_request` — with no `issue` object — do **not** yield an issue number, so the command **`cwd` never switches** to a worktree even when `worktrees` and `load` are set.
3. The hook command has a **`load` directive** (issue-context-aware commands).
4. The event is not `issues.closed` / `issues.deleted` for **creation** (close events skip creating a worktree; cleanup still runs).

Matching logic lives in `hookshot.matcher`; see [Explanation: Architecture](../explanation/architecture.md).

## Configuration

```yaml
worktrees:
  path: .hookshot/worktrees
  setup: uv sync
  teardown: ''
```

- **`path`** — Directory under which per-issue directories are created (e.g. `issue-22`).
- **`setup`** — Optional shell command run once when the worktree is first created (environment expanded).
- **`teardown`** — Optional shell command before removing the worktree on issue close.

## Example hook that runs in a worktree

```yaml
hooks:
  issue_comment.created:
    - command: "git status"
      load:
        key: "issue:${{ repository.full_name }}:${{ issue.number }}"
```

Without `load`, `cwd` stays default even if `worktrees` is set.

## Cleanup

Configure hooks on `issues.closed` (or rely on your automation) so issue state and worktrees align. Close events trigger worktree removal when `worktrees` is enabled.

## See also

- [Reference: Worktrees](../reference/worktrees.md)
- [Reference: Configuration](../reference/configuration.md)
