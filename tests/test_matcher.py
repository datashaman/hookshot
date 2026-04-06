"""Tests for event matching logic."""

from unittest.mock import patch

from hookshot.matcher import match_and_run


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
