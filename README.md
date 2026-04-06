# Hookshot

GitHub webhook receiver that runs shell commands from a YAML config. Supports template expressions, conditional execution, persistent state, reusable agents, and automatic `gh webhook forward` setup.

## Install

```bash
pip install .
```

## Quick start

```bash
# Create a starter config in the current directory
hookshot init

# Start the server
HOOKSHOT_SECRET=your-webhook-secret hookshot serve
```

`hookshot init` auto-detects your repository via `gh repo view` and writes a `hookshot.yml` with placeholder hooks.

## Config

Hookshot searches for configuration in this order:

1. `./hookshot.yml` in the current directory (project-specific)
2. `~/.config/hookshot/hooks.yml` (global default, platform-specific via `platformdirs`)

You can override with `--config`:

```bash
hookshot serve --config /path/to/hooks.yml
```

### Minimal example

```yaml
secret: "${HOOKSHOT_SECRET}"

listen:
  host: 0.0.0.0
  port: 9876

hooks:
  push:
    - command: "echo 'Push to ${{ repository.full_name }} on ${{ ref }}'"
```

### Environment variables

Use `${VAR_NAME}` in `secret`, `repo`, and `state_file` fields to inject values from the environment. Missing variables resolve to empty string.

## Template syntax

Use `${{ dotpath }}` to reference values from the GitHub webhook payload:

- `${{ repository.full_name }}` resolves to `org/repo`
- `${{ pull_request.head.ref }}` resolves to `feature-branch`
- `${{ sender.login }}` resolves to `username`

Missing keys resolve to empty string.

### Pipe filters

Filters transform resolved values using pipe syntax:

```
${{ dotpath | filter_name arg }}
```

Available filters:

| Filter | Description | Example |
|--------|-------------|---------|
| `contains <arg>` | `"true"` if value contains arg (case-insensitive) | `${{ issue.title \| contains bug }}` |
| `not_contains <arg>` | `"true"` if value does NOT contain arg | `${{ comment.body \| not_contains skip }}` |
| `eq <arg>` | `"true"` if value equals arg (case-insensitive) | `${{ action \| eq opened }}` |
| `neq <arg>` | `"true"` if value does NOT equal arg | `${{ sender.type \| neq Bot }}` |
| `lower` | Convert to lowercase | `${{ issue.title \| lower }}` |
| `upper` | Convert to uppercase | `${{ ref \| upper }}` |

Filters are commonly used in `if` conditions to gate command execution.

## Conditional execution

Use `if` to conditionally run commands. A single string or a list of conditions is supported. When a list is provided, **all** conditions must be truthy for the command to run.

```yaml
hooks:
  pull_request.closed:
    - command: "deploy.sh"
      if: "${{ pull_request.merged }}"

  issue_comment.created:
    - command: "handle-comment.sh"
      if:
        - "${{ sender.type | neq Bot }}"
        - "${{ comment.body | contains @deploy }}"
```

Falsy values: empty string, `false`, `False`, `null`, `None`, `0`.

## Event matching

Events are matched by name, with optional action qualifiers:

- `push` — matches all push events
- `pull_request` — matches all pull_request actions
- `pull_request.closed` — matches only pull_request with action `closed`

### Comma-separated event keys

A single hook entry can match multiple events:

```yaml
hooks:
  "pull_request.opened, pull_request.reopened":
    - command: "echo 'PR opened or reopened'"
```

Each event in the comma-separated list is matched independently.

## stdin field

The `stdin` field pipes template-expanded text into a command's standard input. This is useful for passing payload data to scripts or tools that read from stdin:

```yaml
hooks:
  issues.opened:
    - command: "my-processor"
      stdin: |
        Issue #${{ issue.number }}: ${{ issue.title }}
        Body: ${{ issue.body }}
```

The `stdin` value is template-expanded before being piped to the command.

## Agents

The top-level `agents` key defines reusable command templates. Hooks reference agents by name instead of repeating `command` and `stdin` definitions:

```yaml
agents:
  notify:
    command: "curl -X POST https://hooks.slack.com/..."
    stdin: '{"text": "${{ repository.full_name }}: ${{ action }}"}'

  deploy:
    command: "deploy.sh"

hooks:
  push:
    - agent: notify
    - agent: deploy

  pull_request.opened:
    - agent: notify
      stdin: '{"text": "New PR: ${{ pull_request.title }}"}'  # overrides agent stdin
```

Agent fields (`command`, `stdin`) are copied to the hook entry. Hook-level fields take precedence, so you can override agent defaults per hook.

## State storage

Hookshot provides persistent key-value state storage for cross-event continuity. State is backed by a JSON file with file-level locking for concurrent access.

### Store directive

Save data after a successful command (exit code 0):

```yaml
hooks:
  issues.opened:
    - command: "echo 'Processing issue'"
      store:
        key: "issue:${{ repository.full_name }}:${{ issue.number }}"
        values:
          title: "${{ issue.title }}"
          author: "${{ sender.login }}"
        log: "Issue opened by ${{ sender.login }}: ${{ issue.title }}"
```

- `key`: Template-expanded identifier for the state bucket
- `values`: Dict of template-expanded key-value pairs, merged into the bucket
- `log`: Template-expanded string appended to the bucket's log array

### Load directive

Load state into the template context as `state.*`:

```yaml
hooks:
  issue_comment.created:
    - command: "echo 'Issue ${{ state.title }} by ${{ state.author }}'"
      load:
        key: "issue:${{ repository.full_name }}:${{ issue.number }}"
```

Loaded state exposes all stored `values` as `state.<key>` and the full log as `state.context` (log entries joined with newlines).

### Clear directive

Delete state buckets after a successful command:

```yaml
hooks:
  issues.closed:
    - command: "echo 'Cleaning up'"
      clear:
        - "issue:${{ repository.full_name }}:${{ issue.number }}"
```

Patterns ending with `*` delete all keys with that prefix.

## gh webhook forward integration

When `repo` is set in the config, hookshot automatically sets up GitHub webhook forwarding using the `gh` CLI:

```yaml
repo: owner/repo-name
secret: "${HOOKSHOT_SECRET}"
```

On startup, hookshot will:

1. Verify `gh` CLI is installed
2. Install the `gh-webhook` extension if missing
3. Derive the required event list from your configured hooks
4. Spawn `gh webhook forward --repo=owner/repo-name --events=push,pull_request,... --url=http://localhost:<port>`

### GhForwardSupervisor

The forwarding process is monitored by `GhForwardSupervisor`, which automatically restarts it on failure with exponential backoff:

- Initial delay: 5 seconds
- Maximum delay: 300 seconds (5 minutes)
- Maximum consecutive failures: 10 (then gives up)
- Failure counter resets when the process runs successfully

Omit `repo` to use direct webhooks instead (requires manual GitHub webhook configuration).

## CLI commands

```bash
hookshot init                    # Create starter hookshot.yml
hookshot serve                   # Start the webhook server
hookshot serve --config FILE     # Use a specific config file
hookshot validate                # Validate config for errors
hookshot test EVENT PAYLOAD      # Simulate an event (dry-run)
hookshot test EVENT @file.json   # Simulate from a file
hookshot state list              # List all state keys
hookshot state get KEY           # Show values and log for a key
hookshot state clear PATTERN     # Delete state by key or prefix*
```

### hookshot init

Creates a starter `hookshot.yml` in the current directory. Auto-detects the repository via `gh repo view`.

### hookshot validate

Checks the config for structural errors: invalid repo format, undefined agent references, missing command fields, and malformed directives. Prints a hooks summary on success.

### hookshot test

Simulates a webhook event without GitHub connectivity. Payload can be inline JSON or a file reference with `@`. Useful for validating hook configurations before deployment.

### hookshot state

Inspect and manage persistent state. `list` shows all keys with counts; `get` displays a bucket's values and log; `clear` removes keys by exact match or prefix wildcard (`*`).

## Security

Hookshot verifies the `X-Hub-Signature-256` header using HMAC-SHA256. Requests with missing or invalid signatures are rejected with 403.

The secret supports environment variable expansion: `"${HOOKSHOT_SECRET}"` reads from the `HOOKSHOT_SECRET` env var.

## Full config example

See [`hookshot.yml`](hookshot.yml) in this repository for a real-world example that uses agents, state storage, conditional execution, and comma-separated events to build an AI-powered code review workflow.
