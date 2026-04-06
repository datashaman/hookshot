# Hookshot documentation

Documentation is organized by the [Diátaxis](https://diataxis.fr/) framework: four distinct modes so tutorials stay hands-on, how-tos stay task-focused, reference stays exhaustive, and explanation stays conceptual.

| Mode | You want… | Start here |
|------|-----------|------------|
| **Tutorial** | A guided path from zero to a working setup | [Getting started](tutorials/getting-started.md) |
| **How-to** | Steps for a specific goal | [How-to guides](how-to/) |
| **Reference** | Facts, flags, keys, defaults | [Reference](reference/) |
| **Explanation** | Why things work this way | [Explanation](explanation/architecture.md) |

## Contents

### Tutorials

- [Getting started](tutorials/getting-started.md) — `init`, minimal config, `serve`, verify with `test`
- [Local webhooks with `repo`](tutorials/webhook-forward.md) — end-to-end with `gh webhook forward`

### How-to guides

- [Run an LLM or CLI agent from a hook](how-to/run-agent-from-hook.md)
- [Gate hooks on comments or markers](how-to/gate-on-markers.md)
- [Use worktrees per issue](how-to/use-worktrees-per-issue.md)
- [Tune command timeouts](how-to/tune-timeouts.md)
- [Run behind `gh webhook forward`](how-to/gh-webhook-forward.md)
- [Rotate webhook secrets](how-to/rotate-secrets.md)
- [Debug a hook that never runs](how-to/debug-hook-not-firing.md)
- [Inspect or clear state](how-to/inspect-state.md)
- [Concurrent webhooks and HTTP 202](how-to/concurrent-webhooks.md)

### Reference

- [Defaults](reference/defaults.md) — ports, timeouts, pool size, supervisor
- [Configuration (YAML)](reference/configuration.md)
- [CLI](reference/cli.md)
- [Templates and filters](reference/templates-and-filters.md)
- [Events](reference/events.md)
- [State storage](reference/state.md)
- [HTTP behavior](reference/http.md)
- [Reactions](reference/reactions.md)
- [Worktrees](reference/worktrees.md)
- [GhForwardSupervisor](reference/gh-forward-supervisor.md)

### Explanation

- [Architecture and design](explanation/architecture.md) — locking, async handling, signatures, trade-offs

---

Example config for this repository: [`hookshot.yml`](../hookshot.yml) in the repo root.

Copy-paste **examples** that are checked in CI against `load_config` / `validate_config`: [`docs/examples/`](examples/) (`*.yml`).
