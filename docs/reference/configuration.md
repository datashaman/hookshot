# Reference: Configuration (YAML)

Exhaustive description of supported top-level and per-hook keys as implemented in `hookshot.config` and consumers. Unsupported keys are ignored unless validation explicitly checks them.

## Top-level keys

| Key | Type | Description |
|-----|------|-------------|
| `secret` | string | Webhook HMAC secret; `${VAR}` expanded from environment. If empty/falsy, signature verification is skipped (forwarding-only setups). |
| `listen` | mapping | `host` (default `0.0.0.0`), `port` (default `9876`). |
| `hooks` | mapping | Event key → list of command mappings. |
| `repo` | string | `owner/name`; enables managed `gh webhook forward`. `${VAR}` expanded. |
| `state_file` | string → path | Optional; default see [Defaults](defaults.md). `${VAR}` expanded. |
| `timeout` | int | Global default command timeout (seconds). Must be positive integer if set. Per-hook overrides. |
| `worktrees` | mapping | Optional; see [Worktrees](worktrees.md). |
| `reactions` | mapping | Optional; see [Reactions](reactions.md). |

### Removed / not implemented

- **`agents`**: Older docs described reusable `agents:` blocks. The current codebase does **not** implement agent indirection; each hook entry must include a **`command`** string. YAML anchors or external templating can deduplicate config.

There is **no** `stream` key in the current implementation: command output is captured in full when the process finishes (buffered `stdout`/`stderr`).

## Per-hook keys

| Key | Required | Description |
|-----|----------|-------------|
| `command` | yes | Shell command after template expansion. |
| `stdin` | no | String (often multiline) template; passed as stdin to the process. |
| `if` | no | String or list of strings; all must be truthy after expansion. |
| `timeout` | no | Seconds; overrides global `timeout` for this hook only. |
| `load` | no | `{ key: "<template>" }`; loads state before expansion; enables worktree cwd when `worktrees` configured. |
| `store` | no | `{ key, values?, log? }`; runs after successful exit `0`. |
| `clear` | no | List of key templates; prefix `*` supported; runs after success. |

## Environment expansion

Expanded early in `load_config` for: `secret`, `state_file`, `repo`, `worktrees.setup`, `worktrees.teardown`. Missing variables become empty string.

## Validation (`hookshot validate`)

Reports: bad `repo` format; invalid `timeout`; hook lists missing `command`; malformed `store` / `load` / `clear`; unsafe `worktrees.path`; invalid `reactions` keys or emoji names.

## See also

- [CLI](cli.md)
- [State](state.md)
- [Templates and filters](templates-and-filters.md)
