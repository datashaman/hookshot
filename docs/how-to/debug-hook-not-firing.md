# How to debug a hook that never runs

**Goal:** Narrow down why a GitHub event does not execute your command.

## Checklist

1. **Event name and action**
   - Hook keys must match [Events](../reference/events.md): either the base event (`issues`) or a qualified name (`issues.opened`).
   - If you use `issues.opened` but GitHub sends `action: opened` under `X-GitHub-Event: issues`, matching must align with how Hookshot builds the qualified name (event + payload `action`).

2. **`if` conditions**
   - Any false condition skips the command. Use `hookshot test` with a saved payload or trimmed JSON to see `[dry-run]` skip lines in logs.

3. **Comma-separated keys**
   - `"pull_request.opened, pull_request.reopened"` matches if **any** listed key matches.

4. **Signature and 403**
   - If verification fails, the handler never runs hooks. Check secret alignment.

5. **Worktree failures**
   - If `worktrees` is on and creating the worktree raises `RuntimeError`, the command is skipped and an error is logged.

6. **Async handling**
   - The HTTP response returns **202** before commands finish. Check Hookshot logs for `Webhook work started` / `finished`, not only the HTTP response.

## Reproduce locally

```bash
hookshot test <event.key> @payload.json
```

Use `-v` for debug logging.

## See also

- [Concurrent webhooks and HTTP 202](concurrent-webhooks.md)
- [Inspect or clear state](inspect-state.md)
