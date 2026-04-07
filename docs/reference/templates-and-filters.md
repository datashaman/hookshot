# Reference: Templates and filters

## Placeholder syntax

```
${{ dot.path.to.key }}
${{ dot.path | filter }}
${{ dot.path | filter arg }}
```

- Resolution uses the GitHub JSON payload, or `state.*` when the path starts with `state.` and `load` provided context.
- Missing keys → empty string.
- Booleans → `"true"` / `"false"`.
- `null` → empty string.

### Wildcard notation

Use `*` to extract a field from each element of an array:

```
${{ issue.labels.*.name }}          → ['bug', 'enhancement']
${{ issue.labels.*.name | any bug }}  → "true"
```

- Only a **single** `*` segment is supported. Multiple wildcards (e.g. `a.*.b.*.c`) log a warning and resolve to an empty string.
- Wildcard results are lists — use `any` or `none` filters for element-wise matching.
- `state.*` paths always resolve to strings (state is a flat key-value store), so wildcard notation does not apply to state paths.

## Pipe filters

| Filter | Arguments | Result |
|--------|-----------|--------|
| `contains` | word | `"true"` if value contains arg (case-insensitive substring) |
| `not_contains` | word | `"true"` if value does **not** contain arg |
| `eq` | word | `"true"` if value equals arg (case-insensitive, trimmed) |
| `neq` | word | `"true"` if value does **not** equal arg |
| `lower` | — | Lowercase |
| `upper` | — | Uppercase |
| `any` | word | `"true"` if any list element equals arg (case-insensitive). Falls back to `eq` for strings. |
| `none` | word | `"true"` if **no** list element equals arg (case-insensitive). Falls back to `neq` for strings. |

Unknown filter names log a warning and return the pre-filter value unchanged (implementation detail).

> **Note:** Applying `contains` or `not_contains` to a wildcard (list) result stringifies the list using Python's repr and does substring matching on that string. This is rarely what you want — use `any` or `none` for element-wise matching instead. A warning is logged when this happens.

### Truthiness for `if`

After expansion, a condition is **falsy** if the string is (case-insensitive): empty, `false`, `null`, `none`, `0`. Everything else is truthy.

## Environment variables in YAML

Separate from `{{<` templates: strings can use `${ENV_VAR}` for keys listed under [Configuration: environment expansion](configuration.md#environment-expansion).

## See also

- [Configuration](configuration.md)
