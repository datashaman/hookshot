# How to run an LLM or CLI agent from a hook

**Goal:** Execute `claude`, `cursor`, `codex`, or any shell command that should read issue or PR context.

## Recipe

1. Put the program invocation in `command` (shell string, after template expansion).
2. Pass structured context on `stdin` using a multiline `stdin` template.
3. Optionally combine with `if` so only certain comments trigger the hook.

## Minimal pattern

```yaml
hooks:
  issues.opened:
    - command: "claude -p --dangerously-skip-permissions --model sonnet"
      stdin: |
        Issue #${{ issue.number }}: ${{ issue.title }}
        ${{ issue.body }}
```

Template rules: [Templates and filters](../reference/templates-and-filters.md).

## Reusable agents

When multiple hooks share the same command and base prompt, define an `agents` block to avoid repetition:

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
  pull_request.synchronize:
    - agent: reviewer
      stdin: |
        Re-review PR #${{ pull_request.number }} after new commits.
```

The agent's base `stdin` is prepended to each hook's `stdin`. The agent's `command` is used automatically. See [Configuration: Agents](../reference/configuration.md#agents) for the full reference.

To generate a complete config with predefined agents, run `hookshot init --workflow` — see [CLI: init](../reference/cli.md#init).

## Practical tips

- **Idempotency:** If the agent posts back to GitHub, use a marker comment (HTML or unique string) and an `if` condition with `not_contains` so you do not loop. See [Gate hooks on markers](gate-on-markers.md).
- **Credentials:** Run Hookshot under an account that already has `gh auth login` and any API keys your agent needs.
- **Timeouts:** Long agent runs may need a higher `timeout` on the hook or globally. See [Tune command timeouts](tune-timeouts.md).
- **Working directory:** For repo-scoped agents per issue, configure [Use worktrees per issue](use-worktrees-per-issue.md).

## See also

- [Reference: Configuration](../reference/configuration.md) (`command`, `stdin`, `timeout`)
- [Explanation: Architecture](../explanation/architecture.md) — command-agnostic core
