"""Event matching logic."""

from __future__ import annotations

import itertools
import logging
import threading
from typing import TYPE_CHECKING

from .runner import run_command
from .worktree import ensure_worktree, extract_issue_number, remove_worktree, worktree_path

if TYPE_CHECKING:
    from .state import StateStore

log = logging.getLogger("hookshot")

# Events that trigger worktree cleanup
_CLOSE_EVENTS = {"issues.closed", "issues.deleted"}

# Serializes command execution per worktree path so two webhook deliveries
# for the same PR/issue never run git operations concurrently in the same
# shared checkout. Keyed by the deterministic worktree path string.
_worktree_locks: dict[str, threading.Lock] = {}
_worktree_locks_guard = threading.Lock()

# Tracks the most recently registered waiter per (worktree_key, dedupe_key),
# so a delivery that is still queued (never started) can be dropped in
# favor of a newer one for the *same* underlying object (e.g. a review
# that GitHub sends as both "submitted" and "edited" seconds apart) without
# ever touching a delivery that has already started running.
_worktree_waiters: dict[str, dict[str, int]] = {}
_worktree_seq = itertools.count()


def _worktree_lock_key(
    commands: list[dict],
    payload: dict,
    qualified: str | None,
    worktrees_config: dict | None,
) -> str | None:
    """Return the deterministic worktree path this batch of commands will use, if any.

    Mirrors the gating logic in ``_resolve_worktree_cwd`` but is cheap and
    side-effect-free (no git calls), so it can be used to pick a lock key
    before any command actually resolves/creates the worktree.
    """
    if not worktrees_config:
        return None
    if qualified in _CLOSE_EVENTS:
        return None
    issue_number = extract_issue_number(payload)
    if issue_number is None:
        return None
    if not any("load" in cmd for cmd in commands):
        return None
    return str(worktree_path(worktrees_config["path"], issue_number))


def _dedupe_key(payload: dict) -> str:
    """Return a stable identity for the object that triggered this delivery.

    Used to recognize when two deliveries are really about the *same*
    underlying review/comment (e.g. GitHub's submitted+edited double-fire)
    rather than two distinct events that both happen to touch the same
    worktree. Falls back to python object identity, which never matches
    another delivery's payload — i.e. "never coalesce" for event shapes
    without a natural identity.
    """
    review = payload.get("review") or {}
    if review.get("id") is not None:
        return f"review:{review['id']}"
    comment = payload.get("comment") or {}
    if comment.get("id") is not None:
        return f"comment:{comment['id']}"
    return f"unique:{id(payload)}"


def _acquire_worktree_slot(worktree_key: str, dedupe_key: str) -> bool:
    """Block until this delivery's turn for ``worktree_key``, or report supersession.

    Returns True if the caller should proceed and must later call
    ``_release_worktree_slot``. Returns False if a newer delivery for the
    same (worktree_key, dedupe_key) registered itself while this one was
    still waiting — in that case the lock has already been released on
    this delivery's behalf and it should skip running entirely.
    """
    with _worktree_locks_guard:
        lock = _worktree_locks.setdefault(worktree_key, threading.Lock())
        waiters = _worktree_waiters.setdefault(worktree_key, {})
        seq = next(_worktree_seq)
        waiters[dedupe_key] = seq

    lock.acquire()

    with _worktree_locks_guard:
        latest = _worktree_waiters.get(worktree_key, {}).get(dedupe_key)
        if latest != seq:
            lock.release()
            return False
    return True


def _release_worktree_slot(worktree_key: str) -> None:
    with _worktree_locks_guard:
        lock = _worktree_locks.get(worktree_key)
    if lock is not None:
        lock.release()


def _resolve_worktree_cwd(
    cmd: dict,
    payload: dict,
    qualified: str | None,
    worktrees_config: dict | None,
    env: dict[str, str] | None = None,
    cache: dict[tuple, str | RuntimeError] | None = None,
) -> str | None:
    """Determine the working directory for a command.

    If worktrees are configured and the command has a load directive with an
    issue key, create/reuse a worktree and return its path.

    ``cache`` memoizes the (base_path, issue_number, branch) -> result for
    the lifetime of one webhook delivery: every command sharing the same
    hook key resolves to the same worktree, so without this each of them
    independently repeats the same git fetch and hits the same failure
    (e.g. a branch already checked out elsewhere) rather than skipping
    the rest of the batch after the first one fails.
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

    # PR payloads (pull_request, pull_request_review) carry the PR's actual
    # head branch — the worktree must resume that branch, not spawn a fresh
    # one, or the reviewer/implementer loop would run against disconnected
    # content instead of the PR being reviewed.
    branch = payload.get("pull_request", {}).get("head", {}).get("ref") or None

    cache_key = (base_path, issue_number, branch)
    if cache is not None and cache_key in cache:
        cached = cache[cache_key]
        if isinstance(cached, RuntimeError):
            raise cached
        return cached

    try:
        wt_path = str(ensure_worktree(base_path, issue_number, setup_command=setup, env=env, branch=branch))
    except RuntimeError as e:
        if cache is not None:
            cache[cache_key] = e
        raise

    if cache is not None:
        cache[cache_key] = wt_path
    return wt_path


def _handle_close_worktree(
    payload: dict,
    qualified: str | None,
    worktrees_config: dict | None,
    env: dict[str, str] | None = None,
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

    # Wait for any in-flight command in this worktree to finish before
    # removing it out from under it. Always proceeds eventually (the
    # dedupe key is unique per call, so it can never be superseded) —
    # it just queues behind whatever is currently running.
    key = str(worktree_path(base_path, issue_number))
    _acquire_worktree_slot(key, f"close:{id(payload)}")
    try:
        remove_worktree(base_path, issue_number, teardown_command=teardown, env=env)
    finally:
        _release_worktree_slot(key)


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
    env: dict[str, str] | None = None,
    notify_on_failure: bool = False,
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
    worktree_cache: dict[tuple, str | RuntimeError] = {}

    log.info("Processing event: %s (action: %s)", event, action or "-")

    for hook_key, commands in hooks.items():
        # Support comma-separated event keys (e.g. "pull_request.opened,pull_request.reopened")
        hook_events = [k.strip() for k in hook_key.split(",")]
        if any(k == qualified or k == event for k in hook_events):
            matched = True
            log.info("Matched hook: %s → %d command(s)", hook_key, len(commands))

            worktree_key = None if dry_run else _worktree_lock_key(commands, payload, qualified, worktrees)
            if worktree_key is not None:
                dedupe_key = _dedupe_key(payload)
                if not _acquire_worktree_slot(worktree_key, dedupe_key):
                    log.info(
                        "  Skipping hook %s — superseded by a newer delivery for the same worktree (%s)",
                        hook_key, worktree_key,
                    )
                    continue

            try:
                for i, cmd in enumerate(commands, 1):
                    try:
                        cwd = _resolve_worktree_cwd(cmd, payload, qualified, worktrees, env, worktree_cache)
                    except RuntimeError:
                        log.error("  Skipping command %d/%d (worktree creation failed): %s", i, len(commands), cmd.get("command", "?"))
                        continue
                    # Don't log the command text here — its "if:" conditions
                    # haven't been checked yet, and a command whose own text
                    # happens to describe a dramatic outcome (e.g. an escalation
                    # comment's --body) reads like a status report on a quick
                    # skim even when it's about to be skipped. run_command logs
                    # the actual text once it knows whether it's running or not
                    # ("Executing: ..." / "Skipped (condition false: ...): ...").
                    log.info("  Checking command %d/%d", i, len(commands))
                    if run_command(
                        cmd,
                        payload,
                        dry_run=dry_run,
                        state=state,
                        reactions=reactions,
                        cwd=cwd,
                        default_timeout=default_timeout,
                        env=env,
                        notify_on_failure=notify_on_failure,
                    ):
                        executed += 1
            finally:
                if worktree_key is not None:
                    _release_worktree_slot(worktree_key)

    # Handle worktree cleanup on issue close (after commands run)
    if not dry_run:
        _handle_close_worktree(payload, qualified, worktrees, env)

    if not matched:
        log.info("No hooks matched event: %s", qualified or event)

    return executed
