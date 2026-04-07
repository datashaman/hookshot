# Hookshot

GitHub webhook receiver that runs shell commands from a YAML config. It supports template expressions, conditional hooks, persistent state (JSON + file locking), optional emoji reactions via `gh`, per-issue git worktrees, and optional `gh webhook forward` when you set `repo`.

## Install

```bash
pip install .
```

## Security (webhooks)

When you set `secret` in config, Hookshot verifies GitHub’s **`X-Hub-Signature-256`** HMAC (SHA-256). The value GitHub signs must match that secret (after `${VAR}` expansion); a mismatch yields **403** `Invalid signature`. Configure the same secret on GitHub (or on `gh webhook forward --secret`). Details: [HTTP reference](docs/reference/http.md) and [Architecture](docs/explanation/architecture.md).

## Documentation

Full documentation uses a **Diátaxis** layout (tutorials, how-to guides, reference, explanation):

**[docs/README.md](docs/README.md)**

Quick path: [Getting started](docs/tutorials/getting-started.md) → `hookshot init --workflow full` → `hookshot serve` → `hookshot test`.

## Repository layout

- **[hookshot.yml](hookshot.yml)** — example configuration for this project using the `agents` abstraction for reusable command/prompt definitions.
- **[docs/](docs/)** — user-facing documentation tree.
