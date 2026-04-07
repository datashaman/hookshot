"""Tests for config loading — agents resolution and validation."""

from hookshot.config import _resolve_agents, validate_config


def test_resolve_agents_expands_command():
    config = {
        "agents": {
            "bot": {"command": "echo hello", "stdin": "base prompt"},
        },
        "hooks": {
            "issues.opened": [
                {"agent": "bot", "stdin": "extra context"},
            ],
        },
    }
    _resolve_agents(config)
    hook = config["hooks"]["issues.opened"][0]
    assert "agent" not in hook
    assert hook["command"] == "echo hello"


def test_resolve_agents_appends_stdin():
    config = {
        "agents": {
            "bot": {"command": "echo", "stdin": "base prompt\n"},
        },
        "hooks": {
            "issues.opened": [
                {"agent": "bot", "stdin": "extra context"},
            ],
        },
    }
    _resolve_agents(config)
    hook = config["hooks"]["issues.opened"][0]
    assert hook["stdin"] == "base prompt\nextra context"


def test_resolve_agents_base_stdin_only():
    config = {
        "agents": {
            "bot": {"command": "echo", "stdin": "base prompt"},
        },
        "hooks": {
            "issues.opened": [
                {"agent": "bot"},
            ],
        },
    }
    _resolve_agents(config)
    hook = config["hooks"]["issues.opened"][0]
    assert hook["stdin"] == "base prompt"


def test_resolve_agents_hook_stdin_only():
    config = {
        "agents": {
            "bot": {"command": "echo"},
        },
        "hooks": {
            "issues.opened": [
                {"agent": "bot", "stdin": "hook only"},
            ],
        },
    }
    _resolve_agents(config)
    hook = config["hooks"]["issues.opened"][0]
    assert hook["stdin"] == "hook only"


def test_resolve_agents_no_agents_is_noop():
    config = {
        "hooks": {
            "issues.opened": [
                {"command": "echo hello"},
            ],
        },
    }
    _resolve_agents(config)
    assert config["hooks"]["issues.opened"][0]["command"] == "echo hello"


def test_resolve_agents_undefined_agent_raises():
    config = {
        "agents": {},
        "hooks": {
            "issues.opened": [
                {"agent": "missing"},
            ],
        },
    }
    try:
        _resolve_agents(config)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "undefined agent" in str(e)


def test_resolve_agents_command_and_agent_raises():
    config = {
        "agents": {
            "bot": {"command": "echo"},
        },
        "hooks": {
            "issues.opened": [
                {"agent": "bot", "command": "override"},
            ],
        },
    }
    try:
        _resolve_agents(config)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "cannot have both" in str(e)


def test_validate_agents_valid():
    config = {
        "hooks": {},
        "agents": {
            "bot": {"command": "echo", "stdin": "hello"},
        },
    }
    errors = validate_config(config)
    assert not errors


def test_validate_agents_missing_command():
    config = {
        "hooks": {},
        "agents": {
            "bot": {"stdin": "hello"},
        },
    }
    errors = validate_config(config)
    assert any("missing 'command'" in e for e in errors)


def test_validate_agents_unknown_key():
    config = {
        "hooks": {},
        "agents": {
            "bot": {"command": "echo", "model": "opus"},
        },
    }
    errors = validate_config(config)
    assert any("unknown key" in e for e in errors)


def test_validate_agents_not_a_dict():
    config = {
        "hooks": {},
        "agents": "bad",
    }
    errors = validate_config(config)
    assert any("must be a mapping" in e for e in errors)


def test_validate_agents_entry_not_a_dict():
    config = {
        "hooks": {},
        "agents": {
            "bot": "bad",
        },
    }
    errors = validate_config(config)
    assert any("must be a mapping" in e for e in errors)
