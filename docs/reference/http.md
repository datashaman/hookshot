# Reference: HTTP behavior

## `POST /` (webhook path)

GitHub POSTs to the server root by default when forwarding to `http://localhost:<port>/`.

| Condition | Status | Body (typical) |
|-----------|--------|----------------|
| Missing `X-GitHub-Event` | 400 | `Missing X-GitHub-Event header` |
| Invalid JSON | 400 | `Invalid JSON` |
| Bad HMAC (when `secret` set) | 403 | `Invalid signature` |
| `X-GitHub-Event: ping` | 200 | `pong` |
| Accepted for processing | **202** | `Accepted — work <id> queued (delivery <id>)` |

The **202** response is sent **after** the delivery is queued to the thread pool; it does **not** wait for shell commands.

## `GET /`

Health check: **200**, body `hookshot ok`. No signature.

## Response body format (202)

Plain text, UTF-8 encoded. Contains:

- Monotonic **work id** (per server process)
- GitHub **delivery** id from `X-GitHub-Delivery` (or `-` if absent)

Use logs for command results, not this body.

## See also

- [Defaults](defaults.md)
- [How-to: concurrent webhooks](../how-to/concurrent-webhooks.md)
