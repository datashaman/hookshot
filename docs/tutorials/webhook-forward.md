# Tutorial: Local webhooks with `repo`

**Goal:** Run Hookshot on your machine and receive real GitHub webhooks via `gh webhook forward`, without exposing a public URL.

Companion to [Getting started](getting-started.md). For supervisor numbers and flags, see [GhForwardSupervisor](../reference/gh-forward-supervisor.md) and [CLI: serve](../reference/cli.md).

## Prerequisites

- Completed [Getting started](getting-started.md) (install, `hookshot init`, `validate`)
- `gh` authenticated (`gh auth status`)
- `repo:` set in `hookshot.yml` to your GitHub repository (`owner/name`)

## Step 1: Confirm event coverage

```bash
hookshot validate
```

Note the printed **GitHub events** list. Hookshot derives it from your hook keys (e.g. `issues.opened` → subscribe to `issues`).

**Checkpoint:** At least one event is listed, or `serve` will error when forwarding starts.

## Step 2: Set your secret

Use the same value GitHub will send (when using `gh webhook forward`, pass the same secret to the CLI — see `gh webhook forward --help`).

```bash
export HOOKSHOT_SECRET='a-long-random-string'
```

Your `hookshot.yml` should reference it, e.g. `secret: "${HOOKSHOT_SECRET}"`.

## Step 3: Start Hookshot

```bash
hookshot serve
```

On startup with `repo` set, Hookshot:

1. Ensures `gh` and the `gh-webhook` extension are available
2. Builds `gh webhook forward --repo=... --events=... --url=http://localhost:<port>` (and `--secret=...` if configured)
3. Spawns that process under a supervisor

**Checkpoint:** Logs show the `gh webhook forward` command line and **Forwarding events:** …

## Step 4: Trigger an event in GitHub

Perform an action that matches a configured hook (open an issue, push, comment, etc.).

**Checkpoint:**

- Hookshot logs show `Accepted webhook … (queued)` then webhook work starting in a worker thread
- Your command runs (or `[dry-run]` only if you used `hookshot test`, not live forward)

## Step 5: Read the response body (optional)

Successful acceptance of a delivery returns **HTTP 202** with a short text body (work id and delivery id). That is normal: the HTTP handler returns before commands finish. See [HTTP behavior](../reference/http.md) and [Concurrent webhooks](../how-to/concurrent-webhooks.md).

## Troubleshooting

| Problem | What to check |
|--------|----------------|
| `gh CLI not found` | Install `gh` or remove `repo` from config to use manual webhooks |
| Forwarder exits repeatedly | Logs show backoff; see [GhForwardSupervisor](../reference/gh-forward-supervisor.md) |
| 403 Invalid signature | `HOOKSHOT_SECRET` and `gh webhook forward --secret` must match |
| Wrong events | Hook keys must include the events you need; GitHub subscribes at the **base** event name |

## Next steps

- [Run behind gh webhook forward](../how-to/gh-webhook-forward.md) — operational notes
- [Rotate secrets](../how-to/rotate-secrets.md)
