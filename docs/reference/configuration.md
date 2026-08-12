# Reference: Configuration (YAML)

Exhaustive description of supported top-level and per-hook keys as implemented in `hookshot.config` and consumers. Unsupported keys are ignored unless validation explicitly checks them.

## File resolution

When `-c`/`--config` isn't given, Hookshot resolves the config file in this order (first match wins):

1. `--config PATH` / `-c PATH` — explicit path on the command line.
2. `./hookshot.yml` — local override, typically gitignored per-developer.
3. `./hookshot.dist.yml` — committed team baseline.
4. `~/.config/hookshot/hooks.yml` (via platformdirs) — global fallback.

This mirrors PHPUnit's `phpunit.xml` / `phpunit.xml.dist` convention: commit `hookshot.dist.yml` as the shared config for the team, and let individual developers override it locally with an untracked `hookshot.yml` without needing to modify the shared file or pass `--config` every time.

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
| `notify_on_failure` | bool | Optional, default `false`. When `true`, a non-zero exit, timeout, or exception posts a comment on the triggering issue/PR explaining what happened, in addition to the `failed` reaction (if configured). Without it, a failure is visible only via that reaction and `hookshot.log`. |
| `agents` | mapping | Optional; reusable agent definitions. Each key is an agent name mapping to `command` (required) and `stdin` (optional base prompt). Hooks reference agents with `agent: <name>`. See [Agents](#agents) below. |
| `env` | mapping | Optional; declares default environment variables available as `${{ env.NAME }}` in `command`/`stdin`/`if`/`load`/`store`/`clear`. Values are strings (non-scalars rejected) and support `${VAR}` expansion. A variable exported in the real process environment always overrides its declared default. See [Environment expansion](#environment-expansion). |

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

There are two independent mechanisms, kept on disjoint fields so they never collide:

1. **`${VAR}` — load-time, process environment only.** Expanded once in `load_config` for exactly: `secret`, `state_file`, `repo`, `worktrees.setup`, `worktrees.teardown`, and each value in the `env` block itself (so `CLAUDE_BIN: ${MY_CLAUDE}` composes). Missing variables become empty string.
2. **`${{ env.NAME }}` — runtime template, config + process environment.** Works anywhere `${{ }}` templates already work: `command`, `stdin`, `if`, `load.key`, `store.key`/`values`/`log`, `clear`. Resolves against the merged map `{**env_block, **os.environ}` — a name exported at run time overrides its declared default in `env:`; an undeclared name still resolves if it's exported; otherwise it expands to an empty string. See [Templates and filters](templates-and-filters.md#environment-variables).

`hookshot validate` warns (but does not fail) about any `${{ env.NAME }}` reference that is neither declared in `env:` nor set in the process environment — validation must not depend on the ambient environment to pass/fail.

## `.env` files

Before loading the config, Hookshot loads `./.env` (or `--env-file PATH`) into the process environment via `hookshot.config.load_dotenv`. This is what makes `CLAUDE_BIN=claude-beta` in a local `.env` reach both mechanisms above (`${VAR}` and `${{ env.NAME }}`) without exporting it in your shell first.

- Format: `KEY=VALUE` per line; blank lines and `#` comments are skipped; a leading `export ` is stripped; values may be wrapped in matching single or double quotes.
- **A variable already exported in the process environment is left untouched** — `.env` only supplies a default, so `CLAUDE_BIN=claude-next hookshot serve` still overrides whatever `.env` says.
- No-op if the file doesn't exist — `.env` is optional.
- This is separate from the config's own `env:` block (see above); `.env` populates `os.environ` itself, so declared `env:` defaults and `${VAR}` expansion see it too.

## Validation (`hookshot validate`)

Reports: bad `repo` format; invalid `timeout`; hook lists missing `command`; malformed `store` / `load` / `clear`; unsafe `worktrees.path`; invalid `reactions` keys or emoji names; undefined agent references; hooks with both `agent` and `command`; invalid agent definitions; invalid `env` keys/values. Also **warns** (non-fatal) about `${{ env.NAME }}` references with no declared default and no matching process environment variable.

## See also

- [CLI](cli.md)
- [State](state.md)
- [Templates and filters](templates-and-filters.md)
