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

## Pipe filters

| Filter | Arguments | Result |
|--------|-----------|--------|
| `contains` | word | `"true"` if value contains arg (case-insensitive substring) |
| `not_contains` | word | `"true"` if value does **not** contain arg |
| `eq` | word | `"true"` if value equals arg (case-insensitive, trimmed) |
| `neq` | word | `"true"` if value does **not** equal arg |
| `lower` | — | Lowercase |
| `upper` | — | Uppercase |

Unknown filter names log a warning and return the pre-filter value unchanged (implementation detail).

### Truthiness for `if`

After expansion, a condition is **falsy** if the string is (case-insensitive): empty, `false`, `null`, `none`, `0`. Everything else is truthy.

## Environment variables in YAML

Separate from `{{<` templates: strings can use `${ENV_VAR}` for keys listed under [Configuration: environment expansion](configuration.md#environment-expansion).

## See also

- [Configuration](configuration.md)
