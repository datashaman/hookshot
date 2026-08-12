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
        - "${{ review.body | contains <!-- hookshot:reviewer --> }}"
        - "${{ review.body | not_contains <!-- hookshot:approved --> }}"
```

The reviewer includes `<!-- hookshot:approved -->` when satisfied, which causes the `not_contains` condition to fail, stopping the loop.

Match the **full HTML comment**, not the bare word (`contains hookshot:reviewer` instead of `contains <!-- hookshot:reviewer -->`). A review or comment body that merely *discusses* a marker in prose — an adversarial reviewer describing your marker setup, for instance — contains the bare word too, and would satisfy a bare-word condition by accident. Only the literal `<!-- hookshot:X -->` comment is reliably the actual marker, since that's the exact string every agent prompt is instructed to emit as its trailing footer.

## Capping a review loop

`not_contains hookshot:approved` stops the loop when the reviewer approves, but nothing stops it if reviewer and implementer keep disagreeing — it's unbounded by default. Add a turn counter using the `add`/`lt`/`gte` filters ([reference](../reference/templates-and-filters.md)) on top of the marker gate, and a one-shot escalation command once the cap is hit:

```yaml
hooks:
  pull_request_review.submitted, pull_request_review.edited:
    - agent: implementer
      if:
        - "${{ review.body | contains <!-- hookshot:reviewer --> }}"
        - "${{ review.body | not_contains <!-- hookshot:approved --> }}"
        - "${{ state.loop_count | lt 4 }}"
      load:
        key: "pr:${{ repository.full_name }}:${{ pull_request.number }}"
      store:
        key: "pr:${{ repository.full_name }}:${{ pull_request.number }}"
        values:
          loop_count: "${{ state.loop_count | add 1 }}"

    # ... the symmetric reviewer-follow-up command, same loop_count gate ...

    # Fires once, when the cap is first crossed
    - command: "gh pr comment ${{ pull_request.number }} --repo ${{ repository.full_name }} --body 'Loop capped — needs a human.'"
      if:
        - "${{ review.body | not_contains <!-- hookshot:approved --> }}"
        - "${{ state.loop_count | gte 4 }}"
        - "${{ state.escalated | neq true }}"
      load:
        key: "pr:${{ repository.full_name }}:${{ pull_request.number }}"
      store:
        key: "pr:${{ repository.full_name }}:${{ pull_request.number }}"
        values:
          escalated: "true"
```

Without the `escalated` guard, the escalation command re-fires on *every* subsequent review event once the count is capped (it never un-crosses `gte 4`), not just the first — worth checking with a dry run (`hookshot test`) or a small simulation before trusting a capped-loop config in production.

The `hookshot init` templates (`pr-review`, `full`) include this pattern by default at a cap of 4.

## Common patterns

| Intent | Sketch |
|--------|--------|
| Human only | `if: "${{ sender.type | neq Bot }}"` |
| Keyword gate | `contains @deploy` |
| Avoid feedback loops | `not_contains <!-- hookshot:agent -->` (or your project marker, as the full HTML comment) |
| Bot-only path | `eq Bot` on `sender.type` |
| Break review loop on approval | `not_contains <!-- hookshot:approved -->` |
| Cap a review loop | `state.loop_count | lt 4` alongside the approval gate; see [above](#capping-a-review-loop) |

## See also

- [Reference: Templates and filters](../reference/templates-and-filters.md)
- Example: [`hookshot.yml`](../../hookshot.yml) in this repository
