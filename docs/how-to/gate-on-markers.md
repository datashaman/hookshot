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
hooks:
  issue_comment.created:
    - command: "./handle.sh"
      if:
        - "${{ sender.type | neq Bot }}"
        - "${{ comment.body | contains @implement }}"
        - "${{ comment.body | not_contains hookshot:agent }}"
```

After template expansion, Hookshot treats these strings as truthy/falsy. Rules: [Templates and filters](../reference/templates-and-filters.md#truthiness-for-if).

## Breaking review loops

The generated workflow templates use HTML comment markers to coordinate multi-agent feedback loops. Four markers are conventional:

| Marker | Purpose |
|--------|---------|
| `<!-- hookshot:agent -->` | Generic bot marker — all agent comments include this to prevent self-triggering. |
| `<!-- hookshot:reviewer -->` | Identifies a review submitted by the reviewer agent. |
| `<!-- hookshot:implementer -->` | Identifies a comment from the implementer agent. |
| `<!-- hookshot:approved -->` | Signals approval — breaks the reviewer/implementer loop. |

**Example: reviewer triggers implementer, but not after approval**

```yaml
hooks:
  pull_request_review.submitted:
    - agent: implementer
      if:
        - "${{ review.body | contains hookshot:reviewer }}"
        - "${{ review.body | not_contains hookshot:approved }}"
```

The reviewer includes `<!-- hookshot:approved -->` when satisfied, which causes the `not_contains` condition to fail, stopping the loop.

## Common patterns

| Intent | Sketch |
|--------|--------|
| Human only | `if: "${{ sender.type | neq Bot }}"` |
| Keyword gate | `contains @deploy` |
| Avoid feedback loops | `not_contains hookshot:agent` (or your project marker) |
| Bot-only path | `eq Bot` on `sender.type` |
| Break review loop on approval | `not_contains hookshot:approved` |

## See also

- [Reference: Templates and filters](../reference/templates-and-filters.md)
- Example: [`hookshot.yml`](../../hookshot.yml) in this repository
