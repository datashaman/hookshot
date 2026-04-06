# Reference: Events

## Matching rules

- GitHub sends `X-GitHub-Event` (e.g. `issues`, `pull_request`).
- The payload may include `action` (e.g. `opened`, `closed`).
- Hookshot builds `qualified = f"{event}.{action}"` when `action` is non-empty.

Each hook **key** in YAML may be:

- A single event key: `push`, `pull_request`, `issues.opened`, …
- Comma-separated keys: `"pull_request.opened, pull_request.reopened"` — matched if **any** entry matches.

### Match algorithm

For each comma-separated key `k`:

- Match if `k == qualified`, e.g. `issues.opened` matches event `issues` and action `opened`.
- Match if `k == event` with no action suffix, e.g. `pull_request` matches **any** pull_request action.

## Subscription vs matching

`hookshot config.get_events` maps hook keys to **base** GitHub event names for `gh webhook forward --events=…` (text before the first `.` in each comma-split key). GitHub does not subscribe to `opened` separately — you subscribe to `issues` and filter actions in Hookshot.

## See also

- [Explanation: Architecture](../explanation/architecture.md)
