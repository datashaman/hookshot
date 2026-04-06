# How to gate hooks on comments or markers

**Goal:** Run a hook only when a human says `@implement`, only when the body lacks a bot marker, or combine several conditions.

## Single condition

```yaml
hooks:
  issue_comment.created:
    - command: "./handle.sh"
      if: "${{ comment.body | contains @implement }}"
```

## All conditions must pass (AND)

```yaml
      if:
        - "${{ sender.type | neq Bot }}"
        - "${{ comment.body | contains @implement }}"
        - "${{ comment.body | not_contains hookshot:agent }}"
```

After template expansion, Hookshot treats these strings as truthy/falsy. Rules: [Templates and filters](../reference/templates-and-filters.md#truthiness-for-if).

## Common patterns

| Intent | Sketch |
|--------|--------|
| Human only | `if: "${{ sender.type | neq Bot }}"` |
| Keyword gate | `contains @deploy` |
| Avoid feedback loops | `not_contains hookshot:agent` (or your project marker) |
| Bot-only path | `eq Bot` on `sender.type` |

## See also

- [Reference: Templates and filters](../reference/templates-and-filters.md)
- Example: [`hookshot.yml`](../../hookshot.yml) in this repository
