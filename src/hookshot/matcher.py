"""Event matching logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .runner import run_command

if TYPE_CHECKING:
    from .state import StateStore

log = logging.getLogger("hookshot")


def match_and_run(
    hooks: dict,
    event: str,
    payload: dict,
    *,
    dry_run: bool = False,
    state: StateStore | None = None,
) -> int:
    """Match a GitHub event against configured hooks and run matching commands.

    Event matching:
    - "push" matches X-GitHub-Event: push (any action)
    - "pull_request.closed" matches X-GitHub-Event: pull_request with action: closed
    - "pull_request" matches X-GitHub-Event: pull_request with ANY action

    Returns the number of commands executed.
    """
    action = payload.get("action", "")
    qualified = f"{event}.{action}" if action else None

    executed = 0

    log.info("Processing event: %s (action: %s)", event, action or "-")

    for hook_key, commands in hooks.items():
        # Match: exact qualified name, or bare event name
        if hook_key == qualified or hook_key == event:
            log.info("Matched hook: %s → %d command(s)", hook_key, len(commands))
            for i, cmd in enumerate(commands, 1):
                log.info("  Running command %d/%d: %s", i, len(commands), cmd.get("command", "?"))
                if run_command(cmd, payload, dry_run=dry_run, state=state):
                    executed += 1

    if not executed:
        log.info("No hooks matched event: %s", qualified or event)

    return executed
