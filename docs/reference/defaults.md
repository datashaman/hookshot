# Defaults (canonical)

Values enforced or assumed by Hookshot unless overridden in config or CLI.

| Item | Default | Config / code |
|------|---------|----------------|
| Config file (first found) | `./hookshot.yml` | Then `~/.config/hookshot/hooks.yml` via platformdirs |
| Listen host | `0.0.0.0` | `listen.host` |
| Listen port | `9876` | `listen.port` |
| State file | User data dir `hookshot/state.json` | `state_file` |
| Global command timeout fallback | `300` seconds | Used when neither top-level `timeout` nor per-hook `timeout` is set (`DEFAULT_COMMAND_TIMEOUT`) |
| Webhook worker threads | `8` | `hookshot.server._DEFAULT_WORKER_THREADS` (not configurable via YAML today) |
| POST success response | **202** | Text body includes work id and `X-GitHub-Delivery` |
| Health check | **200** | Body: `hookshot ok` |
| Ping event | **200** | Body: `pong` |
| Invalid signature | **403** | Body: `Invalid signature` |
| GhForwardSupervisor initial restart delay | `5` s | `INITIAL_DELAY` |
| GhForwardSupervisor max backoff | `300` s | `MAX_DELAY` |
| GhForwardSupervisor max consecutive failures | `10` | `MAX_RETRIES` |
| Reaction API subprocess timeout | `30` s | `hookshot.reactions` |

If a default changes in code, update this table in the same commit.
