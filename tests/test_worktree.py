"""Tests for git worktree management."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hookshot.worktree import (
    ensure_worktree,
    extract_issue_number,
    remove_worktree,
    worktree_path,
    _is_valid_worktree,
)
from hookshot.matcher import match_and_run, _resolve_worktree_cwd, _handle_close_worktree
from hookshot.config import validate_config


# --- worktree_path ---

@patch("hookshot.worktree._git_repo_root")
def test_worktree_path_relative(mock_root):
    mock_root.return_value = Path("/repo")
    assert worktree_path(".hookshot/worktrees", 42) == Path("/repo/.hookshot/worktrees/issue-42")


def test_worktree_path_absolute():
    assert worktree_path("/tmp/worktrees", 42) == Path("/tmp/worktrees/issue-42")


@patch("hookshot.worktree._git_repo_root")
def test_worktree_path_string_number(mock_root):
    mock_root.return_value = Path("/repo")
    assert worktree_path(".hookshot/worktrees", "7") == Path("/repo/.hookshot/worktrees/issue-7")


# --- _is_valid_worktree ---

@patch("hookshot.worktree.subprocess.run")
def test_is_valid_worktree_true(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="worktree /tmp/wt/issue-5\nHEAD abc123\nbranch refs/heads/hookshot/issue-5\n\n",
    )
    # Use resolve to match implementation
    path = Path("/tmp/wt/issue-5")
    with patch.object(Path, "resolve", return_value=path):
        assert _is_valid_worktree(path) is True


@patch("hookshot.worktree.subprocess.run")
def test_is_valid_worktree_false(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="worktree /repo\nHEAD abc123\nbranch refs/heads/main\n\n",
    )
    path = Path("/tmp/wt/issue-5")
    with patch.object(Path, "resolve", return_value=path):
        assert _is_valid_worktree(path) is False


# --- extract_issue_number ---

def test_extract_issue_number_from_payload():
    payload = {"issue": {"number": 5}}
    assert extract_issue_number(payload) == 5


def test_extract_issue_number_missing():
    assert extract_issue_number({}) is None
    assert extract_issue_number({"issue": {}}) is None


# --- ensure_worktree ---

@patch("hookshot.worktree._is_valid_worktree", return_value=False)
@patch("hookshot.worktree._git_repo_root", return_value=Path("/repo"))
@patch("hookshot.worktree.subprocess.run")
def test_ensure_worktree_creates_new(mock_run, mock_root, mock_valid, tmp_path):
    base = str(tmp_path / "worktrees")
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    result = ensure_worktree(base, 42)

    assert result == Path(base) / "issue-42"
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[:3] == ["git", "worktree", "add"]
    assert "-b" in args
    assert "hookshot/issue-42" in args


@patch("hookshot.worktree._is_valid_worktree", return_value=True)
@patch("hookshot.worktree._git_repo_root", return_value=Path("/repo"))
@patch("hookshot.worktree.subprocess.run")
def test_ensure_worktree_reuses_existing(mock_run, mock_root, mock_valid, tmp_path):
    base = str(tmp_path / "worktrees")
    wt = Path(base) / "issue-42"
    wt.mkdir(parents=True)

    result = ensure_worktree(base, 42)

    assert result == wt
    mock_run.assert_not_called()


@patch("hookshot.worktree._is_valid_worktree", return_value=False)
@patch("hookshot.worktree._git_repo_root", return_value=Path("/repo"))
@patch("hookshot.worktree.subprocess.run")
def test_ensure_worktree_cleans_invalid_dir(mock_run, mock_root, mock_valid, tmp_path):
    """Directory exists but is not a valid worktree — should be cleaned up."""
    base = str(tmp_path / "worktrees")
    wt = Path(base) / "issue-42"
    wt.mkdir(parents=True)
    (wt / "stale_file").touch()

    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    result = ensure_worktree(base, 42)

    assert result == wt
    mock_run.assert_called_once()


@patch("hookshot.worktree._is_valid_worktree", return_value=False)
@patch("hookshot.worktree._git_repo_root", return_value=Path("/repo"))
@patch("hookshot.worktree.subprocess.run")
def test_ensure_worktree_retries_without_b_flag(mock_run, mock_root, mock_valid, tmp_path):
    base = str(tmp_path / "worktrees")
    fail_result = MagicMock(returncode=128, stderr="already exists")
    ok_result = MagicMock(returncode=0, stdout="", stderr="")
    mock_run.side_effect = [fail_result, ok_result]

    result = ensure_worktree(base, 42)

    assert result == Path(base) / "issue-42"
    assert mock_run.call_count == 2
    # Second call should not have -b
    second_args = mock_run.call_args_list[1][0][0]
    assert "-b" not in second_args
    assert "hookshot/issue-42" in second_args


@patch("hookshot.worktree._is_valid_worktree", return_value=False)
@patch("hookshot.worktree._git_repo_root", return_value=Path("/repo"))
@patch("hookshot.worktree.subprocess.run")
def test_ensure_worktree_runs_setup(mock_run, mock_root, mock_valid, tmp_path):
    base = str(tmp_path / "worktrees")
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    ensure_worktree(base, 42, setup_command="uv sync")

    assert mock_run.call_count == 2
    setup_call = mock_run.call_args_list[1]
    assert setup_call[0][0] == "uv sync"
    assert setup_call[1]["cwd"] == str(Path(base) / "issue-42")
    assert setup_call[1]["shell"] is True


@patch("hookshot.worktree._is_valid_worktree", return_value=False)
@patch("hookshot.worktree._git_repo_root", return_value=Path("/repo"))
@patch("hookshot.worktree.subprocess.run")
def test_ensure_worktree_raises_on_failure(mock_run, mock_root, mock_valid, tmp_path):
    base = str(tmp_path / "worktrees")
    mock_run.return_value = MagicMock(returncode=1, stderr="fatal error")

    with pytest.raises(RuntimeError, match="git worktree add failed"):
        ensure_worktree(base, 42)


@patch("hookshot.worktree._is_valid_worktree", return_value=False)
@patch("hookshot.worktree._git_repo_root", return_value=Path("/repo"))
@patch("hookshot.worktree.subprocess.run")
def test_ensure_worktree_raises_on_setup_failure(mock_run, mock_root, mock_valid, tmp_path):
    """Setup failure should raise RuntimeError, not just warn."""
    base = str(tmp_path / "worktrees")
    git_ok = MagicMock(returncode=0, stdout="", stderr="")
    setup_fail = MagicMock(returncode=1, stderr="uv: error")
    mock_run.side_effect = [git_ok, setup_fail]

    with pytest.raises(RuntimeError, match="Worktree setup failed"):
        ensure_worktree(base, 42, setup_command="uv sync")


# --- remove_worktree ---

@patch("hookshot.worktree._git_repo_root", return_value=Path("/repo"))
@patch("hookshot.worktree.subprocess.run")
def test_remove_worktree_success(mock_run, mock_root, tmp_path):
    base = str(tmp_path / "worktrees")
    wt = Path(base) / "issue-42"
    wt.mkdir(parents=True)
    mock_run.return_value = MagicMock(returncode=0)

    assert remove_worktree(base, 42) is True
    # Should call git worktree remove AND git branch -D
    assert mock_run.call_count == 2
    remove_args = mock_run.call_args_list[0][0][0]
    assert remove_args[:3] == ["git", "worktree", "remove"]
    branch_args = mock_run.call_args_list[1][0][0]
    assert branch_args == ["git", "branch", "-D", "hookshot/issue-42"]


@patch("hookshot.worktree._git_repo_root", return_value=Path("/repo"))
@patch("hookshot.worktree.subprocess.run")
def test_remove_worktree_nonexistent(mock_run, mock_root, tmp_path):
    base = str(tmp_path / "worktrees")
    assert remove_worktree(base, 42) is True
    mock_run.assert_not_called()


@patch("hookshot.worktree._git_repo_root", return_value=Path("/repo"))
@patch("hookshot.worktree.subprocess.run")
def test_remove_worktree_runs_teardown(mock_run, mock_root, tmp_path):
    base = str(tmp_path / "worktrees")
    wt = Path(base) / "issue-42"
    wt.mkdir(parents=True)
    mock_run.return_value = MagicMock(returncode=0)

    remove_worktree(base, 42, teardown_command="make clean")

    # teardown + worktree remove + branch delete
    assert mock_run.call_count == 3
    teardown_call = mock_run.call_args_list[0]
    assert teardown_call[0][0] == "make clean"
    assert teardown_call[1]["cwd"] == str(wt)


# --- _resolve_worktree_cwd ---

@patch("hookshot.matcher.ensure_worktree")
def test_resolve_worktree_cwd_with_load(mock_ensure):
    mock_ensure.return_value = Path("/tmp/wt/issue-5")
    cmd = {"command": "echo hi", "load": {"key": "issue:repo:5"}}
    payload = {"issue": {"number": 5}}
    config = {"path": "/tmp/wt", "setup": None}

    result = _resolve_worktree_cwd(cmd, payload, "issue_comment.created", config)
    assert result == "/tmp/wt/issue-5"
    mock_ensure.assert_called_once_with("/tmp/wt", 5, setup_command=None)


def test_resolve_worktree_cwd_no_config():
    cmd = {"command": "echo hi", "load": {"key": "issue:repo:5"}}
    payload = {"issue": {"number": 5}}
    assert _resolve_worktree_cwd(cmd, payload, "issue_comment.created", None) is None


def test_resolve_worktree_cwd_no_load():
    cmd = {"command": "echo hi"}
    payload = {"issue": {"number": 5}}
    config = {"path": "/tmp/wt", "setup": None}
    assert _resolve_worktree_cwd(cmd, payload, "issue_comment.created", config) is None


def test_resolve_worktree_cwd_no_issue():
    cmd = {"command": "echo hi", "load": {"key": "pr:repo:5"}}
    payload = {"pull_request": {"number": 5}}
    config = {"path": "/tmp/wt", "setup": None}
    assert _resolve_worktree_cwd(cmd, payload, "pull_request.opened", config) is None


def test_resolve_worktree_cwd_close_event():
    cmd = {"command": "echo cleanup", "load": {"key": "issue:repo:5"}}
    payload = {"issue": {"number": 5}}
    config = {"path": "/tmp/wt", "setup": None}
    assert _resolve_worktree_cwd(cmd, payload, "issues.closed", config) is None


def test_resolve_worktree_cwd_deleted_event():
    """issues.deleted should also skip worktree creation."""
    cmd = {"command": "echo cleanup", "load": {"key": "issue:repo:5"}}
    payload = {"issue": {"number": 5}}
    config = {"path": "/tmp/wt", "setup": None}
    assert _resolve_worktree_cwd(cmd, payload, "issues.deleted", config) is None


@patch("hookshot.matcher.ensure_worktree")
def test_resolve_worktree_cwd_raises_on_failure(mock_ensure):
    """RuntimeError should propagate, not be caught silently."""
    mock_ensure.side_effect = RuntimeError("git worktree add failed")
    cmd = {"command": "echo hi", "load": {"key": "issue:repo:5"}}
    payload = {"issue": {"number": 5}}
    config = {"path": "/tmp/wt", "setup": None}

    with pytest.raises(RuntimeError):
        _resolve_worktree_cwd(cmd, payload, "issue_comment.created", config)


# --- _handle_close_worktree ---

@patch("hookshot.matcher.remove_worktree")
def test_handle_close_worktree(mock_remove):
    payload = {"issue": {"number": 5}}
    config = {"path": "/tmp/wt", "teardown": "make clean"}
    _handle_close_worktree(payload, "issues.closed", config)
    mock_remove.assert_called_once_with("/tmp/wt", 5, teardown_command="make clean")


@patch("hookshot.matcher.remove_worktree")
def test_handle_close_worktree_deleted_event(mock_remove):
    """issues.deleted should also trigger cleanup."""
    payload = {"issue": {"number": 5}}
    config = {"path": "/tmp/wt", "teardown": None}
    _handle_close_worktree(payload, "issues.deleted", config)
    mock_remove.assert_called_once_with("/tmp/wt", 5, teardown_command=None)


@patch("hookshot.matcher.remove_worktree")
def test_handle_close_worktree_not_close_event(mock_remove):
    payload = {"issue": {"number": 5}}
    config = {"path": "/tmp/wt", "teardown": None}
    _handle_close_worktree(payload, "issues.opened", config)
    mock_remove.assert_not_called()


@patch("hookshot.matcher.remove_worktree")
def test_handle_close_worktree_no_config(mock_remove):
    payload = {"issue": {"number": 5}}
    _handle_close_worktree(payload, "issues.closed", None)
    mock_remove.assert_not_called()


# --- match_and_run with worktrees ---

@patch("hookshot.matcher.ensure_worktree")
@patch("hookshot.runner.subprocess.run")
def test_match_and_run_passes_cwd(mock_subprocess, mock_ensure):
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
    mock_ensure.return_value = Path("/tmp/wt/issue-5")

    hooks = {
        "issue_comment.created": [
            {"command": "echo hi", "load": {"key": "issue:repo:5"}},
        ],
    }
    payload = {"action": "created", "issue": {"number": 5}}
    worktrees = {"path": "/tmp/wt", "setup": None}

    match_and_run(hooks, "issue_comment", payload, worktrees=worktrees)

    mock_subprocess.assert_called_once()
    assert mock_subprocess.call_args[1]["cwd"] == "/tmp/wt/issue-5"


@patch("hookshot.matcher.ensure_worktree")
@patch("hookshot.runner.subprocess.run")
def test_match_and_run_skips_on_worktree_failure(mock_subprocess, mock_ensure):
    """If worktree creation fails, the command should be skipped entirely."""
    mock_ensure.side_effect = RuntimeError("git worktree add failed")

    hooks = {
        "issue_comment.created": [
            {"command": "echo hi", "load": {"key": "issue:repo:5"}},
        ],
    }
    payload = {"action": "created", "issue": {"number": 5}}
    worktrees = {"path": "/tmp/wt", "setup": None}

    executed = match_and_run(hooks, "issue_comment", payload, worktrees=worktrees)

    assert executed == 0
    mock_subprocess.assert_not_called()


@patch("hookshot.runner.subprocess.run")
def test_match_and_run_no_worktrees(mock_subprocess):
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

    hooks = {
        "push": [{"command": "echo hi"}],
    }
    payload = {}

    match_and_run(hooks, "push", payload)

    mock_subprocess.assert_called_once()
    assert mock_subprocess.call_args[1]["cwd"] is None


# --- config validation ---

def test_validate_worktrees_valid():
    config = {
        "hooks": {},
        "worktrees": {"path": ".hookshot/worktrees", "setup": "uv sync", "teardown": None},
    }
    assert validate_config(config) == []


def test_validate_worktrees_unknown_key():
    config = {
        "hooks": {},
        "worktrees": {"path": ".hookshot/worktrees", "unknown": "bad"},
    }
    errors = validate_config(config)
    assert len(errors) == 1
    assert "unknown key" in errors[0]


def test_validate_worktrees_not_a_dict():
    config = {
        "hooks": {},
        "worktrees": "bad",
    }
    errors = validate_config(config)
    assert len(errors) == 1
    assert "must be a mapping" in errors[0]


def test_validate_no_worktrees_is_valid():
    config = {"hooks": {}}
    assert validate_config(config) == []


def test_validate_worktrees_unsafe_path_root():
    config = {
        "hooks": {},
        "worktrees": {"path": "/"},
    }
    errors = validate_config(config)
    assert any("unsafe path" in e for e in errors)


def test_validate_worktrees_unsafe_path_dotdot():
    config = {
        "hooks": {},
        "worktrees": {"path": "../../etc"},
    }
    errors = validate_config(config)
    assert any("unsafe path" in e for e in errors)


def test_validate_worktrees_path_not_string():
    config = {
        "hooks": {},
        "worktrees": {"path": 123},
    }
    errors = validate_config(config)
    assert any("must be a string" in e for e in errors)
