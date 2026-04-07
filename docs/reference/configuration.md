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
| `agents` | mapping | Optional; reusable agent definitions. Each key is an agent name mapping to `command` (required) and `stdin` (optional base prompt). Hooks reference agents with `agent: <name>`. See [Agents](#agents) below. |

## Per-hook keys

| Key | Required | Description |
|-----|----------|-------------|
| `command` | yes (unless `agent` used) | Shell command after template expansion. |
| `agent` | no | Name of a defined agent. Mutually exclusive with `command`. Copies the agent's `command` and prepends the agent's base `stdin` to any hook-level `stdin`. |
| `stdin` | no | String (often multiline) template; passed as stdin to the process. When used with `agent`, appended to the agent's base `stdin`. |
| `if` | no | String or list of strings; all must be truthy after expansion. |
| `timeout` | no | Seconds; overrides global `timeout` for this hook only. |
| `load` | no | `{ key: "<template>" }`; loads state before expansion; enables worktree cwd when `worktrees` configured. |
| `store` | no | `{ key, values?, log? }`; runs after successful exit `0`. |
| `stream` | no | Boolean; when `true`, command output is logged line-by-line as it arrives instead of buffered until exit. |
| `clear` | no | List of key templates; prefix `*` supported; runs after success. |

## Agents

Define reusable agent blocks at the top level to avoid duplicating `command` and base `stdin` across hooks.

```yaml
agents:
  reviewer:
    command: "claude -p --model opus"
    stdin: |
      You are a code reviewer. Be thorough and constructive.

hooks:
  pull_request.opened:
    - agent: reviewer
      stdin: |
        Review PR #${{ pull_request.number }}: ${{ pull_request.title }}
```

When a hook references `agent: reviewer`:

1. The agent's `command` is copied into the hook.
2. The agent's base `stdin` is **prepended** to any hook-level `stdin` (joined with a newline).
3. The `agent` key is removed after resolution.

A hook **cannot** have both `agent` and `command` — validation rejects this. Every referenced agent name must exist in the top-level `agents` mapping.

Each agent definition accepts only two keys:

| Key | Required | Description |
|-----|----------|-------------|
| `command` | yes | Shell command string. |
| `stdin` | no | Base prompt prepended to hook-level `stdin`. |

## Environment expansion

Expanded early in `load_config` for: `secret`, `state_file`, `repo`, `worktrees.setup`, `worktrees.teardown`. Missing variables become empty string.

## Validation (`hookshot validate`)

Reports: bad `repo` format; invalid `timeout`; hook lists missing `command`; malformed `store` / `load` / `clear`; unsafe `worktrees.path`; invalid `reactions` keys or emoji names; undefined agent references; hooks with both `agent` and `command`; invalid agent definitions.

## See also

- [CLI](cli.md)
- [State](state.md)
- [Templates and filters](templates-and-filters.md)
