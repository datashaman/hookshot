# Tutorial: Getting started

**Goal:** From an empty directory to a running webhook receiver you can exercise locally.

This page is a **tutorial** (learning-oriented). For exact key names and defaults, see [Reference: Configuration](../reference/configuration.md) and [Defaults](../reference/defaults.md).

## What you will have at the end

- A `hookshot.yml` in your project
- `hookshot serve` listening on a TCP port
- A successful dry-run of a webhook with `hookshot test`

## Prerequisites

- Python 3.10+
- Optional but recommended: [GitHub CLI](https://cli.github.com/) (`gh`) if you want `hookshot init` to detect `owner/repo`

## Step 1: Install

From the hookshot repo or a checkout:

```bash
pip install .
```

Or install your published package the same way you normally install it.

**Checkpoint:** `hookshot --help` prints subcommands (`serve`, `test`, `validate`, `init`, `state`).

## Step 2: Create a config

In an empty or existing project directory:

```bash
hookshot init
```

Hookshot detects `owner/repo` via `gh repo view` (or prompts for it), then asks you to choose a workflow template:

| Workflow | What it sets up |
|----------|-----------------|
| `pr-review` | Adversarial PR review with reviewer/implementer feedback loop. |
| `issue-triage` | Issue analysis, conversation, and `@implement` trigger handling. |
| `full` | Combines both workflows (recommended). |

You can skip the interactive prompt by passing the workflow directly:

```bash
hookshot init --workflow full
```

Use `--force` to overwrite an existing config file.

**Checkpoint:** `hookshot.yml` exists and contains `repo`, `agents`, and `hooks` sections.

## Step 3: Validate

```bash
hookshot validate
```

Fix any reported errors (missing `command`, invalid `repo` format, etc.).

**Checkpoint:** Output ends with `Config OK:` and a summary of hooks.

## Step 4: Start the server

If your config uses a `secret`, export it so expansion works when the file contains `"${HOOKSHOT_SECRET}"`:

```bash
export HOOKSHOT_SECRET='your-webhook-secret'
hookshot serve
```

**Checkpoint:** Logs show the listen address (default `0.0.0.0:9876`) and configured hooks. Leave this terminal open.

## Step 5: Verify without GitHub (dry-run)

In another terminal, same directory and config:

```bash
hookshot test issues.opened '{"action":"opened","issue":{"number":1,"title":"Test","body":"Hi"},"repository":{"full_name":"owner/repo"},"sender":{"login":"you","type":"User"}}'
```

**Checkpoint:** Output says how many commands would run; logs show `[dry-run]` lines for each matched command.

## Step 6 (optional): Hit the health URL

With the server still running:

```bash
curl -s http://127.0.0.1:9876/
```

**Checkpoint:** Response body is `hookshot ok`.

## Success criteria

You can tick all of the following:

- [ ] `hookshot validate` succeeds
- [ ] `hookshot serve` starts without validation errors
- [ ] `hookshot test` with a minimal JSON payload reports matched commands
- [ ] GET `/` returns `hookshot ok`

## Troubleshooting

| Problem | What to check |
|--------|----------------|
| `Config not found` | Run from the directory that has `hookshot.yml`, or pass `--config /path/to/file.yml` |
| Validation fails on `repo` | Must look like `owner/name` (slash, no URL) |
| Commands never run in production | [Debug a hook that never runs](../how-to/debug-hook-not-firing.md); confirm GitHub is posting to your URL and events match [Events](../reference/events.md) |
| Invalid signature (403) | Secret in GitHub (or `gh webhook forward --secret`) must match expanded `secret` in config |

## Next steps

- **Local forwarding:** [Local webhooks with `repo`](webhook-forward.md)
- **Timeouts and long jobs:** [Tune command timeouts](../how-to/tune-timeouts.md)
- **Why the server responds before commands finish:** [Concurrent webhooks and HTTP 202](../how-to/concurrent-webhooks.md)
