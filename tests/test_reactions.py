"""Tests for emoji reactions."""

from unittest.mock import patch, MagicMock

from hookshot.reactions import (
    _reaction_endpoint,
    add_reaction,
    remove_reaction,
)
from hookshot.runner import run_command, _finish_reactions, resolve_command_timeout
from hookshot.config import validate_config


# --- _reaction_endpoint tests ---

def test_endpoint_for_issue_comment():
    payload = {
        "repository": {"full_name": "owner/repo"},
        "comment": {"id": 42},
        "issue": {"number": 1},
    }
    endpoint, obj_id = _reaction_endpoint(payload)
    assert endpoint == "/repos/owner/repo/issues/comments/42/reactions"
    assert obj_id == "42"


def test_endpoint_for_pr_review():
    payload = {
        "repository": {"full_name": "owner/repo"},
        "review": {"id": 99},
        "pull_request": {"number": 5},
    }
    endpoint, obj_id = _reaction_endpoint(payload)
    assert endpoint == "/repos/owner/repo/pulls/5/reviews/99/reactions"
    assert obj_id == "99"


def test_endpoint_for_issue():
    payload = {
        "repository": {"full_name": "owner/repo"},
        "issue": {"number": 7},
    }
    endpoint, obj_id = _reaction_endpoint(payload)
    assert endpoint == "/repos/owner/repo/issues/7/reactions"
    assert obj_id == "7"


def test_endpoint_for_pull_request():
    payload = {
        "repository": {"full_name": "owner/repo"},
        "pull_request": {"number": 3},
    }
    endpoint, obj_id = _reaction_endpoint(payload)
    assert endpoint == "/repos/owner/repo/issues/3/reactions"
    assert obj_id == "3"


def test_endpoint_returns_none_for_empty_payload():
    assert _reaction_endpoint({}) is None


def test_endpoint_returns_none_without_repo():
    payload = {"issue": {"number": 1}}
    assert _reaction_endpoint(payload) is None


# --- add_reaction tests ---

@patch("hookshot.reactions.subprocess.run")
def test_add_reaction_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    payload = {
        "repository": {"full_name": "owner/repo"},
        "issue": {"number": 1},
    }
    assert add_reaction(payload, "eyes") is True
    mock_run.assert_called_once()
    args = mock_run.call_args
    assert "eyes" in args[0][0][-1]  # content=eyes in the gh api call


def test_add_reaction_invalid_content():
    assert add_reaction({}, "invalid_emoji") is False


@patch("hookshot.reactions.subprocess.run")
def test_add_reaction_no_endpoint(mock_run):
    assert add_reaction({}, "eyes") is False
    mock_run.assert_not_called()


# --- remove_reaction tests ---

@patch("hookshot.reactions.subprocess.run")
def test_remove_reaction_success(mock_run):
    import json
    # First call: list reactions, second call: delete
    list_response = MagicMock(
        returncode=0,
        stdout=json.dumps([{"id": 123, "content": "eyes"}]),
    )
    delete_response = MagicMock(returncode=0)
    mock_run.side_effect = [list_response, delete_response]

    payload = {
        "repository": {"full_name": "owner/repo"},
        "issue": {"number": 1},
    }
    assert remove_reaction(payload, "eyes") is True
    assert mock_run.call_count == 2


@patch("hookshot.reactions.subprocess.run")
def test_remove_reaction_not_found(mock_run):
    import json
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([{"id": 1, "content": "heart"}]),
    )
    payload = {
        "repository": {"full_name": "owner/repo"},
        "issue": {"number": 1},
    }
    assert remove_reaction(payload, "eyes") is False


# --- _finish_reactions tests ---

@patch("hookshot.runner.remove_reaction")
@patch("hookshot.runner.add_reaction")
def test_finish_reactions_success(mock_add, mock_remove):
    payload = {"repository": {"full_name": "owner/repo"}, "issue": {"number": 1}}
    reactions = {"working": "eyes", "done": "heart", "failed": "confused"}
    _finish_reactions(payload, reactions, success=True)
    mock_remove.assert_called_once_with(payload, "eyes")
    mock_add.assert_called_once_with(payload, "heart")


@patch("hookshot.runner.remove_reaction")
@patch("hookshot.runner.add_reaction")
def test_finish_reactions_failure(mock_add, mock_remove):
    payload = {"repository": {"full_name": "owner/repo"}, "issue": {"number": 1}}
    reactions = {"working": "eyes", "done": "heart", "failed": "confused"}
    _finish_reactions(payload, reactions, success=False)
    mock_remove.assert_called_once_with(payload, "eyes")
    mock_add.assert_called_once_with(payload, "confused")


@patch("hookshot.runner.remove_reaction")
@patch("hookshot.runner.add_reaction")
def test_finish_reactions_none(mock_add, mock_remove):
    _finish_reactions({}, None, success=True)
    mock_add.assert_not_called()
    mock_remove.assert_not_called()


# --- run_command with reactions ---

@patch("hookshot.runner.remove_reaction")
@patch("hookshot.runner.add_reaction")
@patch("hookshot.runner.subprocess.run")
def test_run_command_adds_reactions_on_success(mock_subprocess, mock_add, mock_remove):
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
    payload = {"repository": {"full_name": "owner/repo"}, "issue": {"number": 1}}
    reactions = {"working": "eyes", "done": "heart", "failed": "confused"}

    run_command({"command": "echo hi"}, payload, reactions=reactions)

    # working reaction added before execution
    mock_add.assert_any_call(payload, "eyes")
    # working removed, done added after
    mock_remove.assert_called_with(payload, "eyes")
    mock_add.assert_any_call(payload, "heart")


@patch("hookshot.runner.remove_reaction")
@patch("hookshot.runner.add_reaction")
@patch("hookshot.runner.subprocess.run")
def test_run_command_adds_failed_reaction(mock_subprocess, mock_add, mock_remove):
    mock_subprocess.return_value = MagicMock(returncode=1, stdout="", stderr="error")
    payload = {"repository": {"full_name": "owner/repo"}, "issue": {"number": 1}}
    reactions = {"working": "eyes", "done": "heart", "failed": "confused"}

    run_command({"command": "false"}, payload, reactions=reactions)

    mock_add.assert_any_call(payload, "eyes")
    mock_remove.assert_called_with(payload, "eyes")
    mock_add.assert_any_call(payload, "confused")


@patch("hookshot.runner.remove_reaction")
@patch("hookshot.runner.add_reaction")
@patch("hookshot.runner.subprocess.run")
def test_run_command_no_reactions_when_not_configured(mock_subprocess, mock_add, mock_remove):
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
    payload = {"repository": {"full_name": "owner/repo"}, "issue": {"number": 1}}

    run_command({"command": "echo hi"}, payload)

    mock_add.assert_not_called()
    mock_remove.assert_not_called()


# --- validate_config reactions ---

def test_validate_reactions_valid():
    config = {
        "hooks": {},
        "reactions": {"working": "eyes", "done": "heart", "failed": "confused"},
    }
    assert validate_config(config) == []


def test_validate_reactions_invalid_content():
    config = {
        "hooks": {},
        "reactions": {"working": "not_a_real_emoji"},
    }
    errors = validate_config(config)
    assert len(errors) == 1
    assert "invalid reaction" in errors[0]


def test_validate_reactions_unknown_key():
    config = {
        "hooks": {},
        "reactions": {"started": "eyes"},
    }
    errors = validate_config(config)
    assert len(errors) == 1
    assert "unknown key" in errors[0]


def test_validate_reactions_not_a_dict():
    config = {
        "hooks": {},
        "reactions": "eyes",
    }
    errors = validate_config(config)
    assert len(errors) == 1
    assert "must be a mapping" in errors[0]


def test_validate_no_reactions_is_valid():
    config = {"hooks": {}}
    assert validate_config(config) == []


# --- validate_config timeout ---

def test_validate_timeout_global_valid():
    assert validate_config({"hooks": {}, "timeout": 600}) == []


def test_validate_timeout_global_invalid():
    errors = validate_config({"hooks": {}, "timeout": -1})
    assert any("timeout" in e and "positive integer" in e for e in errors)


def test_validate_timeout_global_not_bool():
    errors = validate_config({"hooks": {}, "timeout": True})
    assert any("timeout" in e for e in errors)


def test_validate_timeout_per_command_invalid():
    errors = validate_config({
        "hooks": {"push": [{"command": "echo", "timeout": 0}]},
    })
    assert any("timeout" in e and "positive integer" in e for e in errors)


def test_validate_timeout_per_command_valid():
    assert validate_config({
        "hooks": {"push": [{"command": "echo", "timeout": 1800}]},
    }) == []


# --- resolve_command_timeout ---

def test_resolve_command_timeout_precedence():
    assert resolve_command_timeout({}, None) == 300
    assert resolve_command_timeout({}, 600) == 600
    assert resolve_command_timeout({"timeout": 1800}, 600) == 1800


# --- run_command timeout ---

@patch("hookshot.runner.subprocess.run")
def test_run_command_default_timeout_300(mock_subprocess):
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")
    run_command({"command": "echo hi"}, {})
    assert mock_subprocess.call_args.kwargs["timeout"] == 300


@patch("hookshot.runner.subprocess.run")
def test_run_command_respects_global_default_timeout(mock_subprocess):
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")
    run_command({"command": "echo hi"}, {}, default_timeout=600)
    assert mock_subprocess.call_args.kwargs["timeout"] == 600


@patch("hookshot.runner.subprocess.run")
def test_run_command_per_hook_timeout_overrides_global(mock_subprocess):
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")
    run_command(
        {"command": "echo hi", "timeout": 1800},
        {},
        default_timeout=600,
    )
    assert mock_subprocess.call_args.kwargs["timeout"] == 1800
