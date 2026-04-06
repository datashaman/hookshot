# Explanation: Architecture and design

Understanding-oriented background for Hookshot. For exact values, see [Reference: Defaults](../reference/defaults.md).

## Command-agnostic core

Hookshot maps GitHub events to shell commands. It does not embed vendor-specific agent protocols: any behavior comes from your `command`, `stdin`, and external tools. That keeps the core small and lets you swap CLIs without changing Hookshot.

## Why file locking for state

Multiple worker threads can process different webhooks at the same time; each may read or update the JSON state file. A separate lock file with `flock` ensures one writer at a time and consistent read-modify-write sequences without interleaved corruption.

## Why a thread pool and HTTP 202

GitHub expects timely HTTP responses. Long-running shell commands (installs, agents, tests) would risk timeouts or duplicate deliveries if the handler blocked.

The server therefore:

1. Validates and parses synchronously (cheap),
2. Submits work to a **bounded** thread pool,
3. Returns **202 Accepted** with a short body that identifies the queued work.

Trade-off: the HTTP layer cannot report command exit codes; operators use logs.

## Why 202 vs 200

**200** is reserved for `ping` (`pong`) and health checks. **202** signals “accepted for processing” rather than “fully done,” which matches the async execution model and avoids implying all hooks finished.

## Event matching vs GitHub subscriptions

GitHub delivers broad events (`issues`, `pull_request`). Your config may narrow by action (`issues.opened`). Subscription lists for `gh webhook forward` use **base** event names only; Hookshot filters actions locally when matching hook keys.

## Buffered command output

Commands run via `subprocess.run` with captured stdout/stderr; logs appear after the process exits (or times out). There is no first-class line streaming option in the codebase today — simpler code paths and predictable log ordering, at the cost of no live incremental output.

## Reactions and `gh`

Reactions are optional sugar: they shell out to `gh api` so the core stays free of HTTP client dependencies for GitHub’s reaction endpoints.

## See also

- [How-to: concurrent webhooks](../how-to/concurrent-webhooks.md)
- [Reference: HTTP](../reference/http.md)
- [Reference: State](../reference/state.md)
