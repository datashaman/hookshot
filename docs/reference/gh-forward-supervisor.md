# Reference: GhForwardSupervisor

Python class: `hookshot.server.GhForwardSupervisor`.

Spawns `gh webhook forward` and watches the subprocess; restarts on unexpected exit with exponential backoff.

## Constants (code)

| Name | Value | Role |
|------|-------|------|
| `INITIAL_DELAY` | `5` | Seconds before first restart after a failure |
| `MAX_DELAY` | `300` | Cap on backoff delay |
| `MAX_RETRIES` | `10` | Consecutive failures before giving up |

After a successful run period, failure count and delay reset.

## Forward command

Built in `_start_gh_forward`: `gh webhook forward --repo=... --events=... --url=http://localhost:<port>` plus `--secret=...` when configured.

Events list derived from hook keys via `get_events` ([Events](events.md)).

## Lifecycle

- `start()` — spawn process, start watcher thread
- `stop()` — terminate process (server shutdown)

Narrative: [Explanation: Architecture](../explanation/architecture.md).
