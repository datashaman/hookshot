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

## Directives

| Directive | When it runs |
|-----------|----------------|
| `store` | After command exits `0`; merges `values`, appends `log` string if present. |
| `clear` | After command exits `0`; deletes exact key or keys with prefix when pattern ends with `*`. |
| `load` | Before expansion / command; does not mutate storage. |

## See also

- [Configuration](configuration.md)
