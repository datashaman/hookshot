"""Event matching logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .runner import run_command
from .worktree import ensure_worktree, extract_issue_number, remove_worktree

if TYPE_CHECKING:
    from .state import StateStore

log = logging.getLogger("hookshot")

# Events that trigger worktree cleanup
_CLOSE_EVENTS = {"issues.closed", "issues.deleted"}


def _resolve_worktree_cwd(
    cmd: dict,
    payload: dict,
    qualified: str | None,
    worktrees_config: dict | None,
) -> str | None:
    """Determine the working directory for a command.

    If worktrees are configured and the command has a load directive with an
    issue key, create/reuse a worktree and return its path.
    """
    if not worktrees_config:
        return None

    issue_number = extract_issue_number(payload)
    if issue_number is None:
        return None

    # For close events, don't create a worktree — removal is handled separately
    if qualified in _CLOSE_EVENTS:
        return None

    # Only commands with a load directive (issue-context-aware) run in a worktree
    if "load" not in cmd:
        return None

    base_path = worktrees_config["path"]
    setup = worktrees_config.get("setup")

    wt_path = ensure_worktree(base_path, issue_number, setup_command=setup)
    return str(wt_path)


def _handle_close_worktree(
    payload: dict,
    qualified: str | None,
    worktrees_config: dict | None,
) -> None:
    """Remove the worktree when an issue is closed."""
    if not worktrees_config:
        return
    if qualified not in _CLOSE_EVENTS:
        return

    issue_number = extract_issue_number(payload)
    if issue_number is None:
        return

    base_path = worktrees_config["path"]
    teardown = worktrees_config.get("teardown")
    remove_worktree(base_path, issue_number, teardown_command=teardown)


def match_and_run(
    hooks: dict,
    event: str,
    payload: dict,
    *,
    dry_run: bool = False,
    state: StateStore | None = None,
    reactions: dict | None = None,
    worktrees: dict | None = None,
    default_timeout: int | None = None,
) -> int:
    """Match a GitHub event against configured hooks and run matching commands.

    Event matching:
    - "push" matches X-GitHub-Event: push (any action)
    - "pull_request.closed" matches X-GitHub-Event: pull_request with action: closed
    - "pull_request" matches X-GitHub-Event: pull_request with ANY action

    Returns the number of commands executed.

    default_timeout: global command timeout in seconds from config (``timeout``).
        Per-hook ``timeout`` overrides this; if both are unset, 300s is used.
    """
    action = payload.get("action", "")
    qualified = f"{event}.{action}" if action else None

    matched = False
    executed = 0

    log.info("Processing event: %s (action: %s)", event, action or "-")

    for hook_key, commands in hooks.items():
        # Support comma-separated event keys (e.g. "pull_request.opened,pull_request.reopened")
        hook_events = [k.strip() for k in hook_key.split(",")]
        if any(k == qualified or k == event for k in hook_events):
            matched = True
            log.info("Matched hook: %s → %d command(s)", hook_key, len(commands))
            for i, cmd in enumerate(commands, 1):
                try:
                    cwd = _resolve_worktree_cwd(cmd, payload, qualified, worktrees)
                except RuntimeError:
                    log.error("  Skipping command %d/%d (worktree creation failed): %s", i, len(commands), cmd.get("command", "?"))
                    continue
                log.info("  Running command %d/%d: %s", i, len(commands), cmd.get("command", "?"))
                if run_command(
                    cmd,
                    payload,
                    dry_run=dry_run,
                    state=state,
                    reactions=reactions,
                    cwd=cwd,
                    default_timeout=default_timeout,
                ):
                    executed += 1

    # Handle worktree cleanup on issue close (after commands run)
    if not dry_run:
        _handle_close_worktree(payload, qualified, worktrees)

    if not matched:
        log.info("No hooks matched event: %s", qualified or event)

    return executed
