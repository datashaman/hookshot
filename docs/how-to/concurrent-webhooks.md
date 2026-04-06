# How to work with concurrent webhooks and HTTP 202

**Goal:** Understand what Hookshot guarantees when GitHub sends many deliveries at once.

## What happens on each POST

1. The handler verifies the signature (if `secret` is set), parses JSON, reads `X-GitHub-Event` and `X-GitHub-Delivery`.
2. It submits work to a **bounded thread pool** and responds with **202 Accepted** immediately.
3. A worker thread runs `match_and_run`, which may execute multiple shell commands for that delivery.

So: **one delivery** can still run **several** hooks sequentially in the worker; **many deliveries** can be in flight up to the pool size.

## Operator expectations

- **Do not** assume the HTTP response body reflects command exit codes. It only acknowledges enqueue.
- Watch logs (and `hookshot.log` if enabled) for `Webhook work started` / `finished` and per-command outcomes.
- If more webhooks arrive than workers, tasks queue inside the executor until a thread is free.

## Defaults

Thread pool size and response format: [Defaults](../reference/defaults.md) and [HTTP behavior](../reference/http.md).

## See also

- [Explanation: Architecture](../explanation/architecture.md)
