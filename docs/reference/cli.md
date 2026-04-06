# Reference: CLI

```text
hookshot [-h] [-c PATH] [-v] <command> ...
```

## Global options

| Option | Meaning |
|--------|---------|
| `-c`, `--config` | Path to YAML config. Default: `./hookshot.yml` if present, else `~/.config/hookshot/hooks.yml`. |
| `-v`, `--verbose` | Debug logging to stderr and `hookshot.log`. |

## Subcommands

| Command | Purpose |
|---------|---------|
| `serve` | Load config, validate, start HTTP server (`hookshot.server.serve`). |
| `validate` | Load config, print errors or summary of hooks/events. |
| `test EVENT PAYLOAD` | Dry-run: expand templates, evaluate `if`, print what would run. `PAYLOAD` is JSON or `@file.json`. |
| `init` | Create starter `./hookshot.yml` (fails if file exists). |
| `state list` | List state keys with value/log counts. |
| `state get KEY` | Print values and log for one key. |
| `state clear PATTERN` | Delete key or prefix when pattern ends with `*`. |

### `test` event argument

You may pass a qualified name such as `pull_request.closed`. Hookshot splits on the first `.`, sets `payload["action"]` when missing, and matches using the base event name plus action (see [Events](events.md)).

## Exit codes

Non-zero on validation failure, missing files, bad JSON, or user abort during `init`.

## See also

- [Configuration](configuration.md)
