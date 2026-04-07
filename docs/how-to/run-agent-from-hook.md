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

## Practical tips

- **Idempotency:** If the agent posts back to GitHub, use a marker comment (HTML or unique string) and an `if` condition with `not_contains` so you do not loop. See [Gate hooks on markers](gate-on-markers.md).
- **Credentials:** Run Hookshot under an account that already has `gh auth login` and any API keys your agent needs.
- **Timeouts:** Long agent runs may need a higher `timeout` on the hook or globally. See [Tune command timeouts](tune-timeouts.md).
- **Working directory:** For repo-scoped agents per issue, configure [Use worktrees per issue](use-worktrees-per-issue.md).

## See also

- [Reference: Configuration](../reference/configuration.md) (`command`, `stdin`, `timeout`)
- [Explanation: Architecture](../explanation/architecture.md) — command-agnostic core
