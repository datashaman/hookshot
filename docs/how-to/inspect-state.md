# How to inspect or clear state

**Goal:** List keys, read a bucket, or delete stored context from the JSON state file.

## CLI

```bash
hookshot state list
hookshot state get 'issue:owner/repo:42'
hookshot state clear 'issue:owner/repo:42'
hookshot state clear 'issue:owner/repo:*'
```

Use `--config` if the config is not in the default search path.

## Where data lives

Default path: platform user data dir / `hookshot/state.json`, unless `state_file` is set in config. See [State storage](../reference/state.md).

## See also

- [Reference: State](../reference/state.md)
- [Reference: Configuration](../reference/configuration.md) (`store`, `load`, `clear`)
