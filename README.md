# Hookshot

GitHub webhook receiver that runs shell commands from a YAML config. It supports template expressions, conditional hooks, persistent state (JSON + file locking), optional emoji reactions via `gh`, per-issue git worktrees, and optional `gh webhook forward` when you set `repo`.

## Install

```bash
pip install .
```

## Documentation

Full documentation uses a **Diátaxis** layout (tutorials, how-to guides, reference, explanation):

**[docs/README.md](docs/README.md)**

Quick path: [Getting started](docs/tutorials/getting-started.md) → `hookshot init` → `hookshot serve` → `hookshot test`.

## Repository layout

- **[hookshot.yml](hookshot.yml)** — example configuration for this project (agents workflow via explicit `command` / `stdin` entries — there is no top-level **`agents`** indirection in Hookshot today).
- **[docs/](docs/)** — user-facing documentation tree.
