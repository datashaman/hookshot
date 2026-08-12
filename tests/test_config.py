"""Tests for config loading — agents resolution and validation."""

from pathlib import Path

import yaml

from hookshot.config import (
    DEFAULT_CONFIG_PATH,
    _resolve_agents,
    find_config,
    load_config,
    resolved_env,
    unresolved_env_refs,
    validate_config,
)


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


# --- find_config: resolution order ---


def test_find_config_prefers_local_over_dist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hookshot.yml").write_text("hooks: {}\n")
    (tmp_path / "hookshot.dist.yml").write_text("hooks: {}\n")
    assert find_config() == Path("hookshot.yml")


def test_find_config_falls_back_to_dist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hookshot.dist.yml").write_text("hooks: {}\n")
    assert find_config() == Path("hookshot.dist.yml")


def test_find_config_falls_back_to_global_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert find_config() == DEFAULT_CONFIG_PATH


# --- env block: load_config normalization ---


def test_load_config_env_block_defaults_to_empty(tmp_path):
    path = tmp_path / "hookshot.yml"
    path.write_text(yaml.dump({"hooks": {}}))
    config = load_config(path)
    assert config["env"] == {}


def test_load_config_env_block_coerces_to_strings(tmp_path):
    path = tmp_path / "hookshot.yml"
    path.write_text(yaml.dump({"hooks": {}, "env": {"CLAUDE_MODEL": "opus", "PORT": 9876}}))
    config = load_config(path)
    assert config["env"] == {"CLAUDE_MODEL": "opus", "PORT": "9876"}


def test_load_config_env_block_expands_var_references(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_CLAUDE", "/opt/claude-beta")
    path = tmp_path / "hookshot.yml"
    path.write_text(yaml.dump({"hooks": {}, "env": {"CLAUDE_BIN": "${MY_CLAUDE}"}}))
    config = load_config(path)
    assert config["env"]["CLAUDE_BIN"] == "/opt/claude-beta"


# --- resolved_env ---


def test_resolved_env_uses_declared_default_when_unset(monkeypatch):
    monkeypatch.delenv("CLAUDE_BIN", raising=False)
    config = {"env": {"CLAUDE_BIN": "claude"}}
    assert resolved_env(config)["CLAUDE_BIN"] == "claude"


def test_resolved_env_process_env_overrides_default(monkeypatch):
    monkeypatch.setenv("CLAUDE_BIN", "claude-next")
    config = {"env": {"CLAUDE_BIN": "claude"}}
    assert resolved_env(config)["CLAUDE_BIN"] == "claude-next"


def test_resolved_env_missing_env_block_is_empty_defaults(monkeypatch):
    monkeypatch.setenv("HOME", "/home/x")
    config = {}
    assert resolved_env(config)["HOME"] == "/home/x"


# --- validate_config: env ---


def test_validate_env_valid():
    config = {"hooks": {}, "env": {"CLAUDE_BIN": "claude", "PORT": 9876}}
    errors = validate_config(config)
    assert not errors


def test_validate_env_not_a_mapping():
    config = {"hooks": {}, "env": "bad"}
    errors = validate_config(config)
    assert any("'env' must be a mapping" in e for e in errors)


def test_validate_env_invalid_name():
    config = {"hooks": {}, "env": {"1-bad-name": "x"}}
    errors = validate_config(config)
    assert any("invalid name" in e for e in errors)


def test_validate_env_nested_value_rejected():
    config = {"hooks": {}, "env": {"CLAUDE_OPTS": {"nested": "dict"}}}
    errors = validate_config(config)
    assert any("must be a scalar" in e for e in errors)


# --- unresolved_env_refs ---


def test_unresolved_env_refs_flags_unset_var(monkeypatch):
    monkeypatch.delenv("NOPE", raising=False)
    config = {
        "hooks": {
            "issues.opened": [{"command": "${{ env.NOPE }} -p"}],
        },
    }
    assert unresolved_env_refs(config) == ["NOPE"]


def test_unresolved_env_refs_silent_when_declared():
    config = {
        "env": {"CLAUDE_BIN": "claude"},
        "hooks": {
            "issues.opened": [{"command": "${{ env.CLAUDE_BIN }} -p"}],
        },
    }
    assert unresolved_env_refs(config) == []


def test_unresolved_env_refs_silent_when_exported(monkeypatch):
    monkeypatch.setenv("CLAUDE_BIN", "claude-next")
    config = {
        "hooks": {
            "issues.opened": [{"command": "${{ env.CLAUDE_BIN }} -p"}],
        },
    }
    assert unresolved_env_refs(config) == []


def test_unresolved_env_refs_checks_stdin_if_store_clear(monkeypatch):
    monkeypatch.delenv("A", raising=False)
    monkeypatch.delenv("B", raising=False)
    monkeypatch.delenv("C", raising=False)
    monkeypatch.delenv("D", raising=False)
    config = {
        "hooks": {
            "issues.opened": [
                {
                    "command": "echo hi",
                    "stdin": "${{ env.A }}",
                    "if": "${{ env.B }}",
                    "store": {"key": "${{ env.C }}", "values": {}},
                    "clear": ["${{ env.D }}"],
                },
            ],
        },
    }
    assert unresolved_env_refs(config) == ["A", "B", "C", "D"]
