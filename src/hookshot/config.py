"""Config loading and environment variable expansion."""

import os
import re
from pathlib import Path

import platformdirs
import yaml

from .reactions import VALID_REACTIONS

_CONFIG_DIR = Path(platformdirs.user_config_dir("hookshot"))
_DATA_DIR = Path(platformdirs.user_data_dir("hookshot"))

LOCAL_CONFIG_PATH = Path("hookshot.yml")
DEFAULT_CONFIG_PATH = _CONFIG_DIR / "hooks.yml"
DEFAULT_STATE_PATH = _DATA_DIR / "state.json"

# Fallback when neither global nor per-command timeout is set (seconds)
DEFAULT_COMMAND_TIMEOUT = 300


def _is_positive_int(value: object) -> bool:
    """True if value is a positive integer (not bool)."""
    return type(value) is int and value > 0


def expand_env(value: str) -> str:
    """Expand ${ENV_VAR} references in a string."""
    return re.sub(
        r"\$\{([^}]+)\}",
        lambda m: os.environ.get(m.group(1), ""),
        value,
    )


def find_config() -> Path:
    """Find the config file: ./hookshot.yml first, then global default."""
    if LOCAL_CONFIG_PATH.exists():
        return LOCAL_CONFIG_PATH
    return DEFAULT_CONFIG_PATH


def load_config(path: Path | None = None) -> dict:
    """Load and validate the hooks config file."""
    path = path or find_config()

    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path) as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"Config must be a YAML mapping, got {type(config).__name__}")

    # Expand env vars in secret
    if "secret" in config:
        config["secret"] = expand_env(str(config["secret"]))

    # Expand env vars in state_file and resolve to Path
    if "state_file" in config:
        config["state_file"] = Path(expand_env(str(config["state_file"])))
    else:
        config["state_file"] = DEFAULT_STATE_PATH

    # Defaults
    config.setdefault("listen", {})
    config["listen"].setdefault("host", "0.0.0.0")
    config["listen"].setdefault("port", 9876)

    config.setdefault("hooks", {})

    # Worktree defaults
    if "worktrees" in config:
        wt = config["worktrees"]
        if not isinstance(wt, dict):
            wt = {}
            config["worktrees"] = wt
        wt.setdefault("path", ".hookshot/worktrees")
        if "setup" in wt:
            wt["setup"] = expand_env(str(wt["setup"])).strip() or None
        else:
            wt["setup"] = None
        if "teardown" in wt:
            wt["teardown"] = expand_env(str(wt["teardown"])).strip() or None
        else:
            wt["teardown"] = None

    # Expand env vars in repo
    if "repo" in config:
        config["repo"] = expand_env(str(config["repo"]))

    return config


def get_events(config: dict) -> list[str]:
    """Extract the unique base GitHub event names from configured hooks.

    Qualified names like "pull_request.closed" are mapped back to "pull_request"
    since GitHub subscribes at the event level, not the action level.
    """
    events = set()
    for hook_key in config.get("hooks", {}):
        # Support comma-separated event keys
        for key in hook_key.split(","):
            base_event = key.strip().split(".")[0]
            events.add(base_event)
    return sorted(events)


def validate_config(config: dict) -> list[str]:
    """Return a list of validation errors (empty = valid)."""
    errors = []

    # repo format: owner/name
    repo = config.get("repo", "")
    if repo and not re.match(r"^[\w.-]+/[\w.-]+$", repo):
        errors.append(f"'repo' must be in owner/name format, got '{repo}'")

    if "timeout" in config and config["timeout"] is not None:
        if not _is_positive_int(config["timeout"]):
            errors.append("'timeout' must be a positive integer (seconds)")

    hooks = config.get("hooks", {})
    if not isinstance(hooks, dict):
        errors.append("'hooks' must be a mapping of event names to command lists")
        return errors

    for event, commands in hooks.items():
        if not isinstance(commands, list):
            errors.append(f"hooks.{event}: must be a list of commands")
            continue
        for i, cmd in enumerate(commands):
            if not isinstance(cmd, dict):
                errors.append(f"hooks.{event}[{i}]: must be a mapping with 'command' key")
                continue
            if "command" not in cmd:
                errors.append(f"hooks.{event}[{i}]: missing 'command' key")

            if "timeout" in cmd:
                if not _is_positive_int(cmd["timeout"]):
                    errors.append(
                        f"hooks.{event}[{i}].timeout: must be a positive integer (seconds)"
                    )

            # Validate store directive
            if "store" in cmd:
                store = cmd["store"]
                if not isinstance(store, dict):
                    errors.append(f"hooks.{event}[{i}].store: must be a mapping")
                elif "key" not in store:
                    errors.append(f"hooks.{event}[{i}].store: missing 'key'")
                elif not isinstance(store.get("values", {}), dict):
                    errors.append(f"hooks.{event}[{i}].store.values: must be a mapping")
                elif "values" not in store and "log" not in store:
                    errors.append(f"hooks.{event}[{i}].store: needs 'values' and/or 'log'")

            # Validate load directive
            if "load" in cmd:
                load = cmd["load"]
                if not isinstance(load, dict):
                    errors.append(f"hooks.{event}[{i}].load: must be a mapping")
                elif "key" not in load:
                    errors.append(f"hooks.{event}[{i}].load: missing 'key'")

            # Validate clear directive
            if "clear" in cmd:
                clear = cmd["clear"]
                if not isinstance(clear, list):
                    errors.append(f"hooks.{event}[{i}].clear: must be a list")

    # Validate worktrees
    worktrees = config.get("worktrees")
    if worktrees is not None:
        if not isinstance(worktrees, dict):
            errors.append("'worktrees' must be a mapping")
        else:
            valid_wt_keys = {"path", "setup", "teardown"}
            for key in worktrees:
                if key not in valid_wt_keys:
                    errors.append(f"worktrees.{key}: unknown key (expected: path, setup, teardown)")
            wt_path = worktrees.get("path", "")
            if wt_path and not isinstance(wt_path, str):
                errors.append("worktrees.path: must be a string")
            elif isinstance(wt_path, str):
                normalized = str(Path(wt_path).resolve())
                if normalized == "/" or ".." in Path(wt_path).parts:
                    errors.append(f"worktrees.path: unsafe path '{wt_path}'")

    # Validate reactions
    reactions = config.get("reactions")
    if reactions is not None:
        if not isinstance(reactions, dict):
            errors.append("'reactions' must be a mapping")
        else:
            valid_keys = {"working", "done", "failed"}
            for key, value in reactions.items():
                if key not in valid_keys:
                    errors.append(f"reactions.{key}: unknown key (expected: working, done, failed)")
                elif value not in VALID_REACTIONS:
                    errors.append(
                        f"reactions.{key}: invalid reaction '{value}' "
                        f"(valid: {', '.join(sorted(VALID_REACTIONS))})"
                    )

    return errors
