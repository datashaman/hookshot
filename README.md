# Hookshot

GitHub webhook receiver that runs shell commands from a YAML config.

## Install

```bash
pip install .
```

## Config

Create `~/.config/hookshot/hooks.yml`:

```yaml
secret: "${HOOKSHOT_SECRET}"

listen:
  host: 0.0.0.0
  port: 9876

hooks:
  push:
    - command: "echo 'Push to ${{ repository.full_name }} on ${{ ref }}'"

  pull_request.closed:
    - command: "cd /home/forge/myapp && php artisan migrate"
      if: "${{ pull_request.merged }}"

  deployment_status:
    - command: "echo '${{ deployment_status.state }} for ${{ repository.name }}'"

  issues.opened:
    - command: "notify-send 'New issue: ${{ issue.title }}'"
```

## Usage

```bash
# Start the server
HOOKSHOT_SECRET=your-webhook-secret hookshot serve

# Validate config
hookshot validate

# Simulate an event (dry-run)
hookshot test push '{"repository":{"full_name":"org/repo"},"ref":"refs/heads/main"}'

# Simulate from a file
hookshot test push @payload.json

# Custom config path
hookshot serve --config /path/to/hooks.yml
```

## Template syntax

Use `${{ dotpath }}` to reference values from the GitHub webhook payload:

- `${{ repository.full_name }}` → `org/repo`
- `${{ pull_request.head.ref }}` → `feature-branch`
- `${{ sender.login }}` → `username`

Missing keys resolve to empty string.

## Conditions

Use `if` to conditionally run commands:

```yaml
hooks:
  pull_request.closed:
    - command: "deploy.sh"
      if: "${{ pull_request.merged }}"
```

Falsy values: empty string, `false`, `null`, `none`, `0`.

## Event matching

- `push` — matches all push events
- `pull_request` — matches all pull_request actions
- `pull_request.closed` — matches only pull_request with action "closed"

## Security

Hookshot verifies the `X-Hub-Signature-256` header using HMAC-SHA256. Requests with missing or invalid signatures are rejected with 403.

The secret supports environment variable expansion: `"${HOOKSHOT_SECRET}"` reads from the `HOOKSHOT_SECRET` env var.
