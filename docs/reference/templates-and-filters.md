# Reference: Templates and filters

## Placeholder syntax

```
${{ dot.path.to.key }}
${{ dot.path | filter }}
${{ dot.path | filter arg }}
```

- Resolution uses the GitHub JSON payload, or `state.*` when the path starts with `state.` and `load` provided context, or `env.*` for environment variables (see [Environment variables](#environment-variables) below).
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
| `add` | number | value + arg as integers, stringified. Non-numeric or missing value is treated as `0` — the idiom for a counter that starts unset: `${{ state.n \| add 1 }}`. |
| `lt` | number | `"true"` if value < arg as integers. Missing/non-numeric value treated as `0`. |
| `gte` | number | `"true"` if value >= arg as integers. Missing/non-numeric value treated as `0`. |

Unknown filter names log a warning and return the pre-filter value unchanged (implementation detail).

> **Note:** Applying `contains` or `not_contains` to a wildcard (list) result stringifies the list using Python's repr and does substring matching on that string. This is rarely what you want — use `any` or `none` for element-wise matching instead. A warning is logged when this happens.

### Truthiness for `if`

After expansion, a condition is **falsy** if the string is (case-insensitive): empty, `false`, `null`, `none`, `0`. Everything else is truthy.

## Environment variables

Two ways environment variables reach a config, covering different fields — see [Configuration: environment expansion](configuration.md#environment-expansion) for exactly which fields each applies to:

- **`${ENV_VAR}`** — load-time only, process environment only. Used in a handful of top-level fields (`secret`, `repo`, `worktrees.setup`, etc.) and in `env:` block values.
- **`${{ env.NAME }}`** — a template namespace, resolved wherever `${{ }}` placeholders work (`command`, `stdin`, `if`, `load`, `store`, `clear`):

  ```yaml
  env:
    CLAUDE_BIN: claude
    CLAUDE_MODEL: opus

  agents:
    reviewer:
      command: "${{ env.CLAUDE_BIN }} -p --model ${{ env.CLAUDE_MODEL }}"
  ```

  Resolution order: the real process environment always wins over the declared `env:` default, so `CLAUDE_BIN=claude-next hookshot serve` overrides it without touching the config. An undeclared name still resolves if it's exported in the process; otherwise it expands to an empty string, and `hookshot validate` warns about it. Filters compose normally: `${{ env.CLAUDE_MODEL | upper }}`.

  Like every other placeholder, the expanded value is substituted into a command string that runs with `shell=True` and is **not shell-quoted** — avoid putting untrusted or special-character values in `env:` defaults that flow into `command`.

## See also

- [Configuration](configuration.md)
