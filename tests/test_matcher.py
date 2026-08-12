"""Tests for event matching logic."""

import threading
import time
from pathlib import Path
from unittest.mock import patch

from hookshot.matcher import (
    _acquire_worktree_slot,
    _release_worktree_slot,
    _worktree_locks_guard,
    _worktree_seq,
    _worktree_waiters,
    match_and_run,
)


@patch("hookshot.matcher.run_command", return_value=True)
def test_issues_opened_matches(mock_run):
    hooks = {
        "issues.opened, issues.reopened": [
            {"command": "echo hello"},
        ],
    }
    payload = {"action": "opened"}
    count = match_and_run(hooks, "issues", payload)
    assert count == 1
    mock_run.assert_called_once()


@patch("hookshot.matcher.run_command", return_value=True)
def test_issues_reopened_matches_same_hook(mock_run):
    hooks = {
        "issues.opened, issues.reopened": [
            {"command": "echo hello"},
        ],
    }
    payload = {"action": "reopened"}
    count = match_and_run(hooks, "issues", payload)
    assert count == 1
    mock_run.assert_called_once()


@patch("hookshot.matcher.run_command", return_value=True)
def test_unmatched_event_runs_nothing(mock_run):
    hooks = {
        "issues.opened, issues.reopened": [
            {"command": "echo hello"},
        ],
    }
    payload = {"action": "closed"}
    count = match_and_run(hooks, "issues", payload)
    assert count == 0
    mock_run.assert_not_called()


@patch("hookshot.matcher.run_command", return_value=True)
def test_bare_event_matches_any_action(mock_run):
    hooks = {
        "push": [
            {"command": "echo pushed"},
        ],
    }
    payload = {}
    count = match_and_run(hooks, "push", payload)
    assert count == 1


@patch("hookshot.matcher.run_command", return_value=True)
def test_multiple_commands_all_run(mock_run):
    hooks = {
        "issues.opened, issues.reopened": [
            {"command": "echo first"},
            {"command": "echo second"},
        ],
    }
    payload = {"action": "reopened"}
    count = match_and_run(hooks, "issues", payload)
    assert count == 2
    assert mock_run.call_count == 2


@patch("hookshot.matcher.run_command", return_value=True)
def test_match_and_run_passes_default_timeout(mock_run):
    hooks = {"push": [{"command": "echo x"}]}
    match_and_run(hooks, "push", {}, default_timeout=900)
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs.get("default_timeout") == 900


@patch("hookshot.matcher.run_command", return_value=True)
def test_match_and_run_passes_env(mock_run):
    hooks = {"push": [{"command": "echo x"}]}
    env = {"CLAUDE_BIN": "claude-next"}
    match_and_run(hooks, "push", {}, env=env)
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs.get("env") == env


# --- per-worktree lock / supersede primitives ---

def test_acquire_worktree_slot_supersedes_stale_waiter():
    """A queued (not-yet-started) waiter gets dropped when a newer waiter
    registers for the same (worktree_key, dedupe_key) before the lock frees up."""
    key = "test-lock-key-supersede"

    assert _acquire_worktree_slot(key, "holder") is True  # occupies the lock

    b_result = {}

    def b_waiter():
        b_result["value"] = _acquire_worktree_slot(key, "shared-dedupe")

    t = threading.Thread(target=b_waiter)
    t.start()
    time.sleep(0.05)  # let B register itself and block on the lock

    # A newer delivery for the same underlying object registers while B still waits
    with _worktree_locks_guard:
        _worktree_waiters[key]["shared-dedupe"] = next(_worktree_seq)

    _release_worktree_slot(key)  # let A's release wake B
    t.join(timeout=2)

    assert b_result["value"] is False  # B was superseded, never got to run

    # The lock is free again — the superseding delivery can now acquire it
    assert _acquire_worktree_slot(key, "shared-dedupe") is True
    _release_worktree_slot(key)


# --- match_and_run concurrency (per-worktree lock + supersede) ---

@patch("hookshot.matcher.ensure_worktree")
@patch("hookshot.matcher.run_command")
def test_match_and_run_serializes_same_worktree(mock_run_command, mock_ensure):
    """Concurrent deliveries for the same worktree never run overlapping commands."""
    mock_ensure.return_value = Path("/tmp/wt/issue-9")
    active = []
    max_concurrent = []

    def fake_run_command(cmd, payload, **kwargs):
        active.append(1)
        max_concurrent.append(len(active))
        time.sleep(0.05)
        active.pop()
        return True

    mock_run_command.side_effect = fake_run_command

    hooks = {
        "issue_comment.created": [
            {"command": "echo hi", "load": {"key": "issue:repo:9"}},
        ],
    }
    worktrees = {"path": "/tmp/wt", "setup": None}
    results = {}

    def run(pid):
        payload = {"action": "created", "issue": {"number": 9}, "_id": pid}
        results[pid] = match_and_run(hooks, "issue_comment", payload, worktrees=worktrees)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2)

    assert max(max_concurrent) == 1
    assert list(results.values()) == [1, 1, 1]


@patch("hookshot.matcher.ensure_worktree")
@patch("hookshot.matcher.run_command")
def test_match_and_run_drops_superseded_queued_duplicate(mock_run_command, mock_ensure):
    """GitHub's submitted+edited double-fire for the same review: the stale
    queued delivery is dropped, the fresh one runs, in-flight work is untouched."""
    mock_ensure.return_value = Path("/tmp/wt/issue-7")

    holder_running = threading.Event()
    release_holder = threading.Event()
    order = []

    def fake_run_command(cmd, payload, **kwargs):
        if payload.get("_role") == "holder":
            holder_running.set()
            release_holder.wait(timeout=2)
        order.append(payload.get("_role"))
        return True

    mock_run_command.side_effect = fake_run_command

    hooks = {
        "pull_request_review.submitted, pull_request_review.edited": [
            {"command": "echo review", "load": {"key": "pr:repo:7"}},
        ],
    }
    worktrees = {"path": "/tmp/wt", "setup": None}

    def make_payload(role, action):
        return {
            "action": action,
            "pull_request": {"number": 7, "head": {"ref": "feature"}},
            "review": {"id": 100},
            "_role": role,
        }

    results = {}

    def run(role, action):
        results[role] = match_and_run(
            hooks, "pull_request_review", make_payload(role, action), worktrees=worktrees
        )

    t_holder = threading.Thread(target=run, args=("holder", "submitted"))
    t_holder.start()
    holder_running.wait(timeout=2)

    t_stale = threading.Thread(target=run, args=("stale", "edited"))
    t_stale.start()
    time.sleep(0.05)  # let "stale" register itself as a waiter

    t_fresh = threading.Thread(target=run, args=("fresh", "edited"))
    t_fresh.start()
    time.sleep(0.05)  # let "fresh" register and supersede "stale"

    release_holder.set()
    for t in (t_holder, t_stale, t_fresh):
        t.join(timeout=2)

    assert results["holder"] == 1
    assert results["stale"] == 0  # superseded — never ran
    assert results["fresh"] == 1
    assert order == ["holder", "fresh"]


@patch("hookshot.matcher.ensure_worktree")
@patch("hookshot.matcher.run_command")
def test_match_and_run_distinct_reviews_both_run_serialized(mock_run_command, mock_ensure):
    """Two genuinely different reviews queued for the same worktree both
    run (in order) -- only literal duplicates of the same object get dropped."""
    mock_ensure.return_value = Path("/tmp/wt/issue-8")
    order = []
    holder_running = threading.Event()
    release_holder = threading.Event()

    def fake_run_command(cmd, payload, **kwargs):
        role = payload.get("_role")
        if role == "holder":
            holder_running.set()
            release_holder.wait(timeout=2)
        order.append(role)
        return True

    mock_run_command.side_effect = fake_run_command

    hooks = {
        "pull_request_review.submitted": [
            {"command": "echo review", "load": {"key": "pr:repo:8"}},
        ],
    }
    worktrees = {"path": "/tmp/wt", "setup": None}

    def make_payload(role, review_id):
        return {
            "action": "submitted",
            "pull_request": {"number": 8, "head": {"ref": "feature"}},
            "review": {"id": review_id},
            "_role": role,
        }

    results = {}

    def run(role, review_id):
        results[role] = match_and_run(
            hooks, "pull_request_review", make_payload(role, review_id), worktrees=worktrees
        )

    t_holder = threading.Thread(target=run, args=("holder", 1))
    t_holder.start()
    holder_running.wait(timeout=2)

    t_other = threading.Thread(target=run, args=("other", 2))
    t_other.start()
    time.sleep(0.05)

    release_holder.set()
    t_holder.join(timeout=2)
    t_other.join(timeout=2)

    assert results["holder"] == 1
    assert results["other"] == 1
    assert order == ["holder", "other"]
