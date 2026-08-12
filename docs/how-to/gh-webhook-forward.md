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

## Multiple people, one repo

`gh webhook forward` registers its own delivery target on the repo for as long as it runs. If two or more people each run `hookshot serve` against the *same* `repo` at the same time, GitHub delivers every event to each of their forwarders independently — every hook fires once per running instance, so you get duplicate PR comments, duplicate reviews, duplicate branches/PRs, and possibly racing pushes to the same branch.

Pick one:

- **Run a single shared instance** — one bot account or one CI/always-on box forwards for the whole team; everyone else's local `hookshot serve` stays off (or omits `repo`/uses `hookshot test` for dry runs).
- **Scope hooks to a person** if several people genuinely need their own running instance, add a filter to each hook's `if:` list so it only acts on work relevant to that person, e.g.:

  ```yaml
  if:
    - "${{ sender.login | eq your-github-username }}"
  ```

  or, for issue/PR assignment:

  ```yaml
  if:
    - "${{ issue.assignee.login | eq your-github-username }}"
  ```

The generated `hookshot init` config includes a commented note about this near the top of the file.

## See also

- [Tutorial: webhook-forward](../tutorials/webhook-forward.md)
- [Rotate secrets](rotate-secrets.md)
- [Explanation: Architecture](../explanation/architecture.md)
