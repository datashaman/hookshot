# Reference: Reactions

Optional top-level block:

```yaml
reactions:
  working: eyes
  done: rocket
  failed: confused
```

## Keys

| Key | Meaning |
|-----|---------|
| `working` | Added via `gh api` when the command **starts** (if reactable target exists). |
| `done` | After exit code `0`; `working` removed first. |
| `failed` | After non-zero exit, timeout, or exception; `working` removed first. |

## Valid `content` values

GitHub reaction names allowed in code (`VALID_REACTIONS`):

`+1`, `-1`, `laugh`, `confused`, `heart`, `hooray`, `rocket`, `eyes`

Invalid names fail validation at `hookshot validate`; at runtime they log a warning and skip.

## Reactable targets

Implementation resolves an issue, PR, issue comment, or PR review from the payload. If no target is found, reactions are skipped quietly.

## Requirements

`gh` must be installed and authenticated when reactions are used.

## See also

- [Configuration](configuration.md)
