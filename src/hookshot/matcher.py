"""Event matching logic."""

import logging

from .runner import run_command

log = logging.getLogger("hookshot")


def match_and_run(
    hooks: dict,
    event: str,
    payload: dict,
    *,
    dry_run: bool = False,
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

    for hook_key, commands in hooks.items():
        # Match: exact qualified name, or bare event name
        if hook_key == qualified or hook_key == event:
            log.info("Matched hook: %s", hook_key)
            for cmd in commands:
                if run_command(cmd, payload, dry_run=dry_run):
                    executed += 1

    return executed
