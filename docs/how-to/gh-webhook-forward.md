# How to run behind `gh webhook forward`

**Goal:** Operate Hookshot with `repo:` so the forwarder is managed for you, or understand what to do manually without `repo`.

## Managed forwarding (`repo` set)

1. Set `repo: owner/name` and optional `secret` (often `"${HOOKSHOT_SECRET}"`).
2. Run `hookshot serve`.
3. Keep `gh` logged in; the forwarder uses your credentials.

Hookshot derives `--events` from hook keys. Details: [GhForwardSupervisor](../reference/gh-forward-supervisor.md).

## Secret alignment

The HMAC secret GitHub uses for `X-Hub-Signature-256` must match the **expanded** `secret` in your config. When using the CLI forwarder, pass the same value the hook delivery will use.

## Without `repo`

Omit `repo` if you configure the webhook in GitHub pointed at your public URL (or another tunnel). You are responsible for event subscriptions and network reachability.

## See also

- [Tutorial: webhook-forward](../tutorials/webhook-forward.md)
- [Rotate secrets](rotate-secrets.md)
- [Explanation: Architecture](../explanation/architecture.md)
