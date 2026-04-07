# Reference: State storage

## File layout

JSON object: keys are buckets. Each bucket:

```json
{
  "values": { "arbitrary": "string keys" },
  "log": ["append-only", "strings"]
}
```

Default path: see [Defaults](defaults.md).

## Template context after `load`

`state.<name>` resolves from the bucket’s `values`. Additionally `state.context` is all `log` entries joined with newlines.

## Locking

All reads and writes use the same pattern: open a sidecar lock file, `flock(LOCK_EX)`, read/modify JSON, write atomically (`mkstemp` + `os.replace`), unlock.

Corrupt JSON is renamed to `*.corrupt.<unixtime>` and the store starts empty.

## Size limits

To prevent unbounded growth, state enforces two limits:

| Constant | Value | Effect |
|----------|-------|--------|
| `MAX_LOG_ENTRY_LENGTH` | 500 chars | Log entries longer than this are truncated and suffixed with `…`. |
| `MAX_CONTEXT_LENGTH` | 4000 chars | `state.context` (the joined log exposed to templates) keeps only the **newest** entries that fit within this budget. Older entries are silently dropped. |

Truncation happens at write time (for individual entries) and at read time (for context assembly). Values stored via `store.values` are not subject to these limits.

## Directives

| Directive | When it runs |
|-----------|----------------|
| `store` | After command exits `0`; merges `values`, appends `log` string if present. |
| `clear` | After command exits `0`; deletes exact key or keys with prefix when pattern ends with `*`. |
| `load` | Before expansion / command; does not mutate storage. |

## See also

- [Configuration](configuration.md)
