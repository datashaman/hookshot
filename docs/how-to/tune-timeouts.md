# How to tune command timeouts

**Goal:** Allow long-running hooks without hitting the default limit, or cap risky commands.

## Defaults

| Scope | Default |
|-------|---------|
| No global and no per-hook `timeout` | 300 seconds (`DEFAULT_COMMAND_TIMEOUT` in code) |

Canonical table: [Defaults](../reference/defaults.md).

## Global timeout

Top-level `timeout` (seconds, positive integer):

```yaml
timeout: 900

hooks:
  issues.opened:
    - command: "slow-job.sh"
```

Applies to every hook that does not set its own `timeout`.

## Per-hook override

```yaml
hooks:
  issues.opened:
    - command: "quick.sh"
      timeout: 60
    - command: "long.sh"
      timeout: 3600
```

Per-hook wins over global; global wins over the 300s fallback.

## Validation

`hookshot validate` rejects non-positive integer `timeout` values.

## See also

- [Reference: Configuration](../reference/configuration.md)
