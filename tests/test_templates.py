"""Tests for workflow templates."""

import yaml

from hookshot.config import load_config, validate_config
from hookshot.templates import AVAILABLE_WORKFLOWS, generate_template


def test_all_templates_are_valid_yaml():
    for workflow in AVAILABLE_WORKFLOWS:
        content = generate_template(workflow, "owner/repo")
        config = yaml.safe_load(content)
        assert isinstance(config, dict), f"{workflow}: not a dict"
        assert config["repo"] == "owner/repo", f"{workflow}: wrong repo"
        assert "hooks" in config, f"{workflow}: no hooks"
        assert "agents" in config, f"{workflow}: no agents"


def test_all_templates_pass_validation(tmp_path):
    for workflow in AVAILABLE_WORKFLOWS:
        content = generate_template(workflow, "owner/repo")
        config_path = tmp_path / f"{workflow}.yml"
        config_path.write_text(content)
        config = load_config(config_path)
        errors = validate_config(config)
        assert not errors, f"{workflow} validation failed: {errors}"


def test_pr_review_has_expected_hooks():
    content = generate_template("pr-review", "owner/repo")
    config = yaml.safe_load(content)
    hook_keys = list(config["hooks"].keys())
    assert "pull_request.opened, pull_request.reopened" in hook_keys
    assert "issue_comment.created" in hook_keys
    assert "pull_request_review.submitted, pull_request_review.edited" in hook_keys
    assert "pull_request.closed" in hook_keys


def test_issue_triage_has_expected_hooks():
    content = generate_template("issue-triage", "owner/repo")
    config = yaml.safe_load(content)
    hook_keys = list(config["hooks"].keys())
    assert "issues.opened, issues.reopened" in hook_keys
    assert "issue_comment.created" in hook_keys
    assert "issues.closed" in hook_keys


def test_full_has_all_hooks():
    content = generate_template("full", "owner/repo")
    config = yaml.safe_load(content)
    hook_keys = list(config["hooks"].keys())
    assert "issues.opened, issues.reopened" in hook_keys
    assert "pull_request.opened, pull_request.reopened" in hook_keys
    assert "pull_request_review.submitted, pull_request_review.edited" in hook_keys
    assert "pull_request.closed" in hook_keys
    assert "issues.closed" in hook_keys


def test_templates_preserve_template_expressions():
    """Ensure ${{ ... }} expressions survive the Python string formatting."""
    content = generate_template("pr-review", "owner/repo")
    assert "${{ pull_request.number }}" in content
    assert "${{ sender.login }}" in content
    assert "${{ review.body }}" in content
    assert "hookshot:reviewer" in content
    assert "hookshot:approved" in content
