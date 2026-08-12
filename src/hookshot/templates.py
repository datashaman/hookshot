"""Starter workflow templates for hookshot init."""

AVAILABLE_WORKFLOWS = ("pr-review", "issue-triage", "full")

# Shared agents used across workflows
_REVIEWER_AGENT = """\
  reviewer:
    command: "${{{{ env.CLAUDE_BIN }}}} -p --dangerously-skip-permissions --model opus"
    stdin: |
      You are an adversarial code reviewer for the {repo} project.
      Your job is to find problems, not to be polite.

      Review steps:
      1. Parse the PR title/body to find the related issue number (look for "Resolves #N" or "Fix #N")
      2. Fetch the original issue and its comments for full context:
         gh issue view <N> --repo ${{{{ repository.full_name }}}} --comments
      3. Fetch the PR diff (use the PR number from context below)
      4. Read every changed file in full to understand the broader context
      5. Write a brutal, thorough review covering:
         - Does the implementation actually solve the issue as described?
         - Bugs, logic errors, edge cases that will break
         - Security issues (injection, secrets, permissions)
         - Missing error handling that matters
         - Race conditions or concurrency problems
         - Things that will bite us in 6 months (maintenance traps)
         - TEST COVERAGE (BLOCKING): Do the tests adequately cover the changes?
           Are there new code paths without tests? Are edge cases tested?
           Missing or inadequate test coverage is a blocking issue, not a nice-to-have.
           Run the test suite and report the results.
         - Anything the author clearly forgot
      6. Post your review:
         - If the PR needs changes, post with the reviewer marker:
           gh pr review <PR_NUMBER> --repo ${{{{ repository.full_name }}}} --body '<your review>

           <!-- hookshot:reviewer -->' --comment
         - If the PR is already good and needs no changes, approve with the approval marker:
           gh pr review <PR_NUMBER> --repo ${{{{ repository.full_name }}}} --approve --body '<your review>

           <!-- hookshot:approved -->'

      Be direct. No praise sandwiches. If something is fine, skip it.
      Focus on what's wrong or risky.
"""

_IMPLEMENTER_AGENT = """\
  implementer:
    command: "${{{{ env.CLAUDE_BIN }}}} -p --dangerously-skip-permissions --model sonnet"
    stdin: |
      You are the implementer for a PR on the {repo} project.
      Your job is to address feedback — fix bugs, improve code, and push new commits.
      Dismiss anything that's wrong or nitpicky, but explain why.

      Steps:
      1. Parse the PR body to find the related issue number (look for "Resolves #N")
      2. Fetch the original issue for context:
         gh issue view <N> --repo ${{{{ repository.full_name }}}} --comments
      3. Fetch the current PR diff (use the PR number from context below)
      4. Check out the PR branch (use the branch from context below)
      5. Read the reviewed files and address each point from the feedback:
         - Fix legitimate bugs and issues
         - Add missing error handling or tests if warranted
         - For points you disagree with, note why
      6. Run the full test suite
         If any tests fail, fix them before pushing. Do NOT push with failing tests.
      7. Commit and push your changes:
         git add -A && git commit -m 'address review feedback' && git push
      8. Post a response as a PR review comment. Include the marker
         <!-- hookshot:implementer --> at the end:
         gh pr review <PR_NUMBER> --repo ${{{{ repository.full_name }}}} --body '<your response>

         <!-- hookshot:implementer -->' --comment
"""

_ANALYST_AGENT = """\
  analyst:
    command: "${{{{ env.CLAUDE_BIN }}}} -p --dangerously-skip-permissions --model opus"
    stdin: |
      You are analyzing a new GitHub issue for the {repo} project.
      Be concise. Focus on feasibility, affected files, and a clear step-by-step plan.
      Include a "Testing" section that specifies what tests should be written or updated
      to cover the proposed changes.

      Post your analysis and plan as a comment on the issue.
      You MUST include the marker <!-- hookshot:agent --> at the end of your comment:
      gh issue comment ${{{{ issue.number }}}} --repo ${{{{ repository.full_name }}}} --body '<your analysis>

      <!-- hookshot:agent -->'
"""

_CONVERSATIONALIST_AGENT = """\
  conversationalist:
    command: "${{{{ env.CLAUDE_BIN }}}} -p --dangerously-skip-permissions --model sonnet"
    stdin: |
      You are discussing a GitHub issue for the {repo} project.
      Respond thoughtfully. If they ask questions about the plan, clarify.
      If they suggest changes, update your thinking.
      If they provide more context, incorporate it.

      You cannot implement anything from this hook — it only posts a comment.
      Never say you are "proceeding to implement" or that you will push changes;
      that only happens when a human comments @implement. If the plan is settled
      and ready to build, say so and tell them to comment @implement, don't
      imply it's already underway.

      Post your response as a comment on the issue.
      You MUST include the marker <!-- hookshot:agent --> at the end of your comment:
      gh issue comment ${{{{ issue.number }}}} --repo ${{{{ repository.full_name }}}} --body '<your response>

      <!-- hookshot:agent -->'
"""


def _pr_review_template(repo: str) -> str:
    return f"""\
repo: {repo}

# NOTE: If more than one person runs `hookshot serve` against this repo at the
# same time (e.g. everyone forwarding with their own `gh webhook forward`),
# GitHub delivers each event to every running instance — so every hook fires
# once per instance, producing duplicate PR comments/reviews/commits. Either
# run a single shared instance (one bot account, one machine/CI job), or scope
# hooks to one person by adding a filter to their `if:` list, e.g.:
#   if:
#     - "${{{{ sender.login | eq your-github-username }}}}"

# Post a comment on the issue/PR when a command fails (non-zero exit, timeout,
# or exception) — otherwise a failure is visible only via the `failed`
# reaction (if configured) and hookshot.log.
notify_on_failure: true

# Override at run time, e.g. CLAUDE_BIN=claude-next hookshot serve
env:
  CLAUDE_BIN: claude

agents:
{_REVIEWER_AGENT.format(repo=repo)}
{_IMPLEMENTER_AGENT.format(repo=repo)}

hooks:
  # Auto-review when a PR is opened or reopened
  pull_request.opened, pull_request.reopened:
    - agent: reviewer
      stdin: |
        PR #${{{{ pull_request.number }}}}: ${{{{ pull_request.title }}}}
        Author: ${{{{ sender.login }}}}
        Branch: ${{{{ pull_request.head.ref }}}} → ${{{{ pull_request.base.ref }}}}
        Body: ${{{{ pull_request.body }}}}

        Use PR number ${{{{ pull_request.number }}}} for all gh commands.
      store:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
        values:
          pr_number: "${{{{ pull_request.number }}}}"
          pr_title: "${{{{ pull_request.title }}}}"
          pr_author: "${{{{ sender.login }}}}"
          pr_branch: "${{{{ pull_request.head.ref }}}}"
        log: "PR #${{{{ pull_request.number }}}} opened by ${{{{ sender.login }}}}: ${{{{ pull_request.title }}}}"

  issue_comment.created:
    # @review on a PR — trigger adversarial reviewer
    - agent: reviewer
      stdin: |
        A human has requested a fresh review.

        PR #${{{{ issue.number }}}}: ${{{{ issue.title }}}}
        Requested by: ${{{{ sender.login }}}}
        Additional context from their comment:
        ${{{{ comment.body }}}}

        Prior context:
        ${{{{ state.context }}}}

        Use PR number ${{{{ issue.number }}}} for all gh commands.
      if:
        - "${{{{ sender.type | neq Bot }}}}"
        - "${{{{ comment.body | not_contains <!-- hookshot:agent --> }}}}"
        - "${{{{ issue.pull_request.url | neq }}}}"
        - "${{{{ comment.body | starts_with @review }}}}"
      load:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
      store:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
        log: "${{{{ sender.login }}}} requested review on PR #${{{{ issue.number }}}} (comment ${{{{ comment.id }}}})"

    # Human comment on a PR — implementer addresses feedback
    - agent: implementer
      stdin: |
        A human has left feedback on your PR. Address their concerns.

        PR #${{{{ issue.number }}}}: ${{{{ issue.title }}}}
        Comment from ${{{{ sender.login }}}}:
        ${{{{ comment.body }}}}

        Prior context:
        ${{{{ state.context }}}}

        Use PR number ${{{{ issue.number }}}} for all gh commands.
        Branch: ${{{{ state.pr_branch }}}}

        Reply on the PR explaining what you changed.
        You MUST include the marker <!-- hookshot:agent --> at the end of your comment:
        gh pr comment ${{{{ issue.number }}}} --repo ${{{{ repository.full_name }}}} --body '<your response>

        <!-- hookshot:agent -->'
      if:
        - "${{{{ sender.type | neq Bot }}}}"
        - "${{{{ comment.body | not_contains <!-- hookshot:agent --> }}}}"
        - "${{{{ issue.pull_request.url | neq }}}}"
        - "${{{{ comment.body | not_starts_with @review }}}}"
      load:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
      store:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
        log: "${{{{ sender.login }}}} commented on PR #${{{{ issue.number }}}} (comment ${{{{ comment.id }}}})"

  pull_request_review.submitted, pull_request_review.edited:
    # Implementer responds to adversarial review
    - agent: implementer
      stdin: |
        An adversarial reviewer has posted feedback on your PR.

        PR #${{{{ pull_request.number }}}}: ${{{{ pull_request.title }}}}
        Branch: ${{{{ pull_request.head.ref }}}}
        Body: ${{{{ pull_request.body }}}}

        Review from ${{{{ review.user.login }}}}:
        ${{{{ review.body }}}}

        Prior context:
        ${{{{ state.context }}}}

        Use PR number ${{{{ pull_request.number }}}} for all gh commands.
      if:
        - "${{{{ review.body | contains <!-- hookshot:reviewer --> }}}}"
        - "${{{{ review.body | not_contains <!-- hookshot:approved --> }}}}"
        - "${{{{ state.loop_count | lt 4 }}}}"
      load:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
      store:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
        values:
          loop_count: "${{{{ state.loop_count | add 1 }}}}"
        log: "Reviewer ${{{{ review.user.login }}}} posted feedback on PR #${{{{ pull_request.number }}}} (review ${{{{ review.id }}}})"

    # Reviewer does a follow-up review after implementer responds
    - agent: reviewer
      stdin: |
        The implementer has responded to your review and pushed changes.
        Do a follow-up review — check if your concerns were actually addressed.

        PR #${{{{ pull_request.number }}}}: ${{{{ pull_request.title }}}}
        Branch: ${{{{ pull_request.head.ref }}}}

        Implementer's response:
        ${{{{ review.body }}}}

        Prior context:
        ${{{{ state.context }}}}

        Use PR number ${{{{ pull_request.number }}}} for all gh commands.

        Be honest. If it's fixed, say so and approve. If not, be specific about what's still wrong.
      if:
        - "${{{{ review.body | contains <!-- hookshot:implementer --> }}}}"
        - "${{{{ review.body | not_contains <!-- hookshot:approved --> }}}}"
        - "${{{{ state.loop_count | lt 4 }}}}"
      load:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
      store:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
        values:
          loop_count: "${{{{ state.loop_count | add 1 }}}}"
        log: "Implementer ${{{{ review.user.login }}}} responded on PR #${{{{ pull_request.number }}}} (review ${{{{ review.id }}}})"

    # Loop capped at 4 automated turns without approval — hand off to a human, once.
    # The body carries the hookshot:agent marker like every other bot-posted
    # comment — without it, this comment is itself an unmarked PR comment
    # and can satisfy a comment-triggered hook's guard, re-firing the very
    # loop it's meant to stop.
    - command: "gh pr comment ${{{{ pull_request.number }}}} --repo ${{{{ repository.full_name }}}} --body '🛑 **hookshot**: the reviewer/implementer loop has gone 4 turns without approval on this PR. Stopping automated iteration — a human should take it from here.\\n\\n<!-- hookshot:agent -->'"
      if:
        - "${{{{ review.body | not_contains <!-- hookshot:approved --> }}}}"
        - "${{{{ state.loop_count | gte 4 }}}}"
        - "${{{{ state.escalated | neq true }}}}"
      load:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
      store:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
        values:
          escalated: "true"

  # Clean up state when PR is closed
  pull_request.closed:
    - command: "echo 'PR #${{{{ pull_request.number }}}} closed, cleaning up state'"
      clear:
        - "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
"""


def _issue_triage_template(repo: str) -> str:
    return f"""\
repo: {repo}

# NOTE: If more than one person runs `hookshot serve` against this repo at the
# same time (e.g. everyone forwarding with their own `gh webhook forward`),
# GitHub delivers each event to every running instance — so every hook fires
# once per instance, producing duplicate issue comments/branches/PRs. Either
# run a single shared instance (one bot account, one machine/CI job), or scope
# hooks to one person by adding a filter to their `if:` list, e.g.:
#   if:
#     - "${{{{ sender.login | eq your-github-username }}}}"

# Post a comment on the issue/PR when a command fails (non-zero exit, timeout,
# or exception) — otherwise a failure is visible only via the `failed`
# reaction (if configured) and hookshot.log.
notify_on_failure: true

# Override at run time, e.g. CLAUDE_BIN=claude-next hookshot serve
env:
  CLAUDE_BIN: claude

agents:
{_ANALYST_AGENT.format(repo=repo)}
{_CONVERSATIONALIST_AGENT.format(repo=repo)}

hooks:
  # Analyze new issues
  issues.opened, issues.reopened:
    - agent: analyst
      stdin: |
        Issue #${{{{ issue.number }}}}: ${{{{ issue.title }}}}
        Author: ${{{{ sender.login }}}}
        Body: ${{{{ issue.body }}}}
      store:
        key: "issue:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
        values:
          title: "${{{{ issue.title }}}}"
          author: "${{{{ sender.login }}}}"
          number: "${{{{ issue.number }}}}"
        log: "Issue #${{{{ issue.number }}}} opened by ${{{{ sender.login }}}}: ${{{{ issue.title }}}} — fetch full body with: gh issue view ${{{{ issue.number }}}} --repo ${{{{ repository.full_name }}}}"

  issue_comment.created:
    # @implement — create a branch, implement, open PR
    - command: "${{{{ env.CLAUDE_BIN }}}} -p --dangerously-skip-permissions --model sonnet"
      stdin: |
        You are working on a GitHub issue for the {repo} project.

        Context of what has happened so far:
        ${{{{ state.context }}}}

        The user ${{{{ sender.login }}}} has asked you to implement the plan.

        1. Read the plan from the context above
        2. Create a new branch: git checkout -b issue-${{{{ issue.number }}}}
        3. Implement the changes
        4. Write tests for any new or changed functionality
        5. Run the full test suite. If any tests fail, fix them before proceeding.
        6. Commit and push the branch
        7. Open a PR using:
           gh pr create --title 'Fix #${{{{ issue.number }}}}: ${{{{ issue.title }}}}' --body 'Resolves #${{{{ issue.number }}}}'
        8. Comment on the issue with a link to the PR.
           You MUST include the marker <!-- hookshot:agent --> at the end of your comment:
           gh issue comment ${{{{ issue.number }}}} --repo ${{{{ repository.full_name }}}} --body '<your comment with PR link>

           <!-- hookshot:agent -->'
      if:
        - "${{{{ sender.type | neq Bot }}}}"
        - "${{{{ comment.body | not_contains <!-- hookshot:agent --> }}}}"
        - "${{{{ comment.body | starts_with @implement }}}}"
        - "${{{{ issue.pull_request.url | eq }}}}"
      load:
        key: "issue:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
      store:
        key: "issue:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
        log: "${{{{ sender.login }}}} requested implementation (comment ${{{{ comment.id }}}}) — branch issue-${{{{ issue.number }}}}"

    # Any other human comment on an issue — continue the conversation
    - agent: conversationalist
      stdin: |
        Context of what has happened so far:
        ${{{{ state.context }}}}

        A new comment was posted by ${{{{ sender.login }}}}:
        ${{{{ comment.body }}}}
      if:
        - "${{{{ sender.type | neq Bot }}}}"
        - "${{{{ comment.body | not_contains <!-- hookshot:agent --> }}}}"
        - "${{{{ comment.body | not_contains <!-- hookshot:reviewer --> }}}}"
        - "${{{{ comment.body | not_starts_with @implement }}}}"
        - "${{{{ issue.pull_request.url | eq }}}}"
      load:
        key: "issue:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
      store:
        key: "issue:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
        log: "${{{{ sender.login }}}} commented on issue #${{{{ issue.number }}}} (comment ${{{{ comment.id }}}})"

  # Clean up state when issue is closed
  issues.closed:
    - command: "echo 'Issue #${{{{ issue.number }}}} closed, cleaning up state'"
      clear:
        - "issue:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
"""


def _full_template(repo: str) -> str:
    return f"""\
repo: {repo}

# NOTE: If more than one person runs `hookshot serve` against this repo at the
# same time (e.g. everyone forwarding with their own `gh webhook forward`),
# GitHub delivers each event to every running instance — so every hook fires
# once per instance, producing duplicate comments/reviews/branches/PRs. Either
# run a single shared instance (one bot account, one machine/CI job), or scope
# hooks to one person by adding a filter to their `if:` list, e.g.:
#   if:
#     - "${{{{ sender.login | eq your-github-username }}}}"

# Post a comment on the issue/PR when a command fails (non-zero exit, timeout,
# or exception) — otherwise a failure is visible only via the `failed`
# reaction (if configured) and hookshot.log.
notify_on_failure: true

# Override at run time, e.g. CLAUDE_BIN=claude-next hookshot serve
env:
  CLAUDE_BIN: claude

agents:
{_ANALYST_AGENT.format(repo=repo)}
{_REVIEWER_AGENT.format(repo=repo)}
{_IMPLEMENTER_AGENT.format(repo=repo)}
{_CONVERSATIONALIST_AGENT.format(repo=repo)}

hooks:
  # Analyze new issues
  issues.opened, issues.reopened:
    - agent: analyst
      stdin: |
        Issue #${{{{ issue.number }}}}: ${{{{ issue.title }}}}
        Author: ${{{{ sender.login }}}}
        Body: ${{{{ issue.body }}}}
      store:
        key: "issue:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
        values:
          title: "${{{{ issue.title }}}}"
          author: "${{{{ sender.login }}}}"
          number: "${{{{ issue.number }}}}"
        log: "Issue #${{{{ issue.number }}}} opened by ${{{{ sender.login }}}}: ${{{{ issue.title }}}} — fetch full body with: gh issue view ${{{{ issue.number }}}} --repo ${{{{ repository.full_name }}}}"

  issue_comment.created:
    # @implement — create a branch, implement, open PR
    - command: "${{{{ env.CLAUDE_BIN }}}} -p --dangerously-skip-permissions --model sonnet"
      stdin: |
        You are working on a GitHub issue for the {repo} project.

        Context of what has happened so far:
        ${{{{ state.context }}}}

        The user ${{{{ sender.login }}}} has asked you to implement the plan.

        1. Read the plan from the context above
        2. Create a new branch: git checkout -b issue-${{{{ issue.number }}}}
        3. Implement the changes
        4. Write tests for any new or changed functionality
        5. Run the full test suite. If any tests fail, fix them before proceeding.
        6. Commit and push the branch
        7. Open a PR using:
           gh pr create --title 'Fix #${{{{ issue.number }}}}: ${{{{ issue.title }}}}' --body 'Resolves #${{{{ issue.number }}}}'
        8. Comment on the issue with a link to the PR.
           You MUST include the marker <!-- hookshot:agent --> at the end of your comment:
           gh issue comment ${{{{ issue.number }}}} --repo ${{{{ repository.full_name }}}} --body '<your comment with PR link>

           <!-- hookshot:agent -->'
      if:
        - "${{{{ sender.type | neq Bot }}}}"
        - "${{{{ comment.body | not_contains <!-- hookshot:agent --> }}}}"
        - "${{{{ comment.body | starts_with @implement }}}}"
        - "${{{{ issue.pull_request.url | eq }}}}"
      load:
        key: "issue:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
      store:
        key: "issue:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
        log: "${{{{ sender.login }}}} requested implementation (comment ${{{{ comment.id }}}}) — branch issue-${{{{ issue.number }}}}"

    # @review on a PR — trigger adversarial reviewer
    - agent: reviewer
      stdin: |
        A human has requested a fresh review.

        PR #${{{{ issue.number }}}}: ${{{{ issue.title }}}}
        Requested by: ${{{{ sender.login }}}}
        Additional context from their comment:
        ${{{{ comment.body }}}}

        Prior context:
        ${{{{ state.context }}}}

        Use PR number ${{{{ issue.number }}}} for all gh commands.
      if:
        - "${{{{ sender.type | neq Bot }}}}"
        - "${{{{ comment.body | not_contains <!-- hookshot:agent --> }}}}"
        - "${{{{ issue.pull_request.url | neq }}}}"
        - "${{{{ comment.body | starts_with @review }}}}"
      load:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
      store:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
        log: "${{{{ sender.login }}}} requested review on PR #${{{{ issue.number }}}} (comment ${{{{ comment.id }}}})"

    # Human comment on a PR — implementer addresses feedback
    - agent: implementer
      stdin: |
        A human has left feedback on your PR. Address their concerns.

        PR #${{{{ issue.number }}}}: ${{{{ issue.title }}}}
        Comment from ${{{{ sender.login }}}}:
        ${{{{ comment.body }}}}

        Prior context:
        ${{{{ state.context }}}}

        Use PR number ${{{{ issue.number }}}} for all gh commands.
        Branch: ${{{{ state.pr_branch }}}}

        Reply on the PR explaining what you changed.
        You MUST include the marker <!-- hookshot:agent --> at the end of your comment:
        gh pr comment ${{{{ issue.number }}}} --repo ${{{{ repository.full_name }}}} --body '<your response>

        <!-- hookshot:agent -->'
      if:
        - "${{{{ sender.type | neq Bot }}}}"
        - "${{{{ comment.body | not_contains <!-- hookshot:agent --> }}}}"
        - "${{{{ issue.pull_request.url | neq }}}}"
        - "${{{{ comment.body | not_starts_with @review }}}}"
      load:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
      store:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
        log: "${{{{ sender.login }}}} commented on PR #${{{{ issue.number }}}} (comment ${{{{ comment.id }}}})"

    # Any other human comment on an issue — continue the conversation
    - agent: conversationalist
      stdin: |
        Context of what has happened so far:
        ${{{{ state.context }}}}

        A new comment was posted by ${{{{ sender.login }}}}:
        ${{{{ comment.body }}}}
      if:
        - "${{{{ sender.type | neq Bot }}}}"
        - "${{{{ comment.body | not_contains <!-- hookshot:agent --> }}}}"
        - "${{{{ comment.body | not_contains <!-- hookshot:reviewer --> }}}}"
        - "${{{{ comment.body | not_starts_with @implement }}}}"
        - "${{{{ issue.pull_request.url | eq }}}}"
      load:
        key: "issue:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
      store:
        key: "issue:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
        log: "${{{{ sender.login }}}} commented on issue #${{{{ issue.number }}}} (comment ${{{{ comment.id }}}})"

  # Auto-review when a PR is opened or reopened
  pull_request.opened, pull_request.reopened:
    - agent: reviewer
      stdin: |
        PR #${{{{ pull_request.number }}}}: ${{{{ pull_request.title }}}}
        Author: ${{{{ sender.login }}}}
        Branch: ${{{{ pull_request.head.ref }}}} → ${{{{ pull_request.base.ref }}}}
        Body: ${{{{ pull_request.body }}}}

        Use PR number ${{{{ pull_request.number }}}} for all gh commands.
      store:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
        values:
          pr_number: "${{{{ pull_request.number }}}}"
          pr_title: "${{{{ pull_request.title }}}}"
          pr_author: "${{{{ sender.login }}}}"
          pr_branch: "${{{{ pull_request.head.ref }}}}"
        log: "PR #${{{{ pull_request.number }}}} opened by ${{{{ sender.login }}}}: ${{{{ pull_request.title }}}}"

  pull_request_review.submitted, pull_request_review.edited:
    # Implementer responds to adversarial review
    - agent: implementer
      stdin: |
        An adversarial reviewer has posted feedback on your PR.

        PR #${{{{ pull_request.number }}}}: ${{{{ pull_request.title }}}}
        Branch: ${{{{ pull_request.head.ref }}}}
        Body: ${{{{ pull_request.body }}}}

        Review from ${{{{ review.user.login }}}}:
        ${{{{ review.body }}}}

        Prior context:
        ${{{{ state.context }}}}

        Use PR number ${{{{ pull_request.number }}}} for all gh commands.
      if:
        - "${{{{ review.body | contains <!-- hookshot:reviewer --> }}}}"
        - "${{{{ review.body | not_contains <!-- hookshot:approved --> }}}}"
        - "${{{{ state.loop_count | lt 4 }}}}"
      load:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
      store:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
        values:
          loop_count: "${{{{ state.loop_count | add 1 }}}}"
        log: "Reviewer ${{{{ review.user.login }}}} posted feedback on PR #${{{{ pull_request.number }}}} (review ${{{{ review.id }}}})"

    # Reviewer does a follow-up review after implementer responds
    - agent: reviewer
      stdin: |
        The implementer has responded to your review and pushed changes.
        Do a follow-up review — check if your concerns were actually addressed.

        PR #${{{{ pull_request.number }}}}: ${{{{ pull_request.title }}}}
        Branch: ${{{{ pull_request.head.ref }}}}

        Implementer's response:
        ${{{{ review.body }}}}

        Prior context:
        ${{{{ state.context }}}}

        Use PR number ${{{{ pull_request.number }}}} for all gh commands.

        Be honest. If it's fixed, say so and approve. If not, be specific about what's still wrong.
      if:
        - "${{{{ review.body | contains <!-- hookshot:implementer --> }}}}"
        - "${{{{ review.body | not_contains <!-- hookshot:approved --> }}}}"
        - "${{{{ state.loop_count | lt 4 }}}}"
      load:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
      store:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
        values:
          loop_count: "${{{{ state.loop_count | add 1 }}}}"
        log: "Implementer ${{{{ review.user.login }}}} responded on PR #${{{{ pull_request.number }}}} (review ${{{{ review.id }}}})"

    # Loop capped at 4 automated turns without approval — hand off to a human, once.
    # The body carries the hookshot:agent marker like every other bot-posted
    # comment — without it, this comment is itself an unmarked PR comment
    # and can satisfy a comment-triggered hook's guard, re-firing the very
    # loop it's meant to stop.
    - command: "gh pr comment ${{{{ pull_request.number }}}} --repo ${{{{ repository.full_name }}}} --body '🛑 **hookshot**: the reviewer/implementer loop has gone 4 turns without approval on this PR. Stopping automated iteration — a human should take it from here.\\n\\n<!-- hookshot:agent -->'"
      if:
        - "${{{{ review.body | not_contains <!-- hookshot:approved --> }}}}"
        - "${{{{ state.loop_count | gte 4 }}}}"
        - "${{{{ state.escalated | neq true }}}}"
      load:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
      store:
        key: "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"
        values:
          escalated: "true"

  # Clean up state when PR or issue is closed
  pull_request.closed:
    - command: "echo 'PR #${{{{ pull_request.number }}}} closed, cleaning up state'"
      clear:
        - "pr:${{{{ repository.full_name }}}}:${{{{ pull_request.number }}}}"

  issues.closed:
    - command: "echo 'Issue #${{{{ issue.number }}}} closed, cleaning up state'"
      clear:
        - "issue:${{{{ repository.full_name }}}}:${{{{ issue.number }}}}"
"""


def generate_template(workflow: str, repo: str) -> str:
    """Generate a hookshot.yml config from a workflow template."""
    generators = {
        "pr-review": _pr_review_template,
        "issue-triage": _issue_triage_template,
        "full": _full_template,
    }
    return generators[workflow](repo)
