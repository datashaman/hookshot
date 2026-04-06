"""Config loading and environment variable expansion."""

import os
import re
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "hookshot" / "hooks.yml"


def expand_env(value: str) -> str:
    """Expand ${ENV_VAR} references in a string."""
    return re.sub(
        r"\$\{([^}]+)\}",
        lambda m: os.environ.get(m.group(1), ""),
        value,
    )


def load_config(path: Path | None = None) -> dict:
    """Load and validate the hooks config file."""
    path = path or DEFAULT_CONFIG_PATH

    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path) as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"Config must be a YAML mapping, got {type(config).__name__}")

    # Expand env vars in secret
    if "secret" in config:
        config["secret"] = expand_env(str(config["secret"]))

    # Defaults
    config.setdefault("listen", {})
    config["listen"].setdefault("host", "0.0.0.0")
    config["listen"].setdefault("port", 9876)

    config.setdefault("hooks", {})

    return config


def validate_config(config: dict) -> list[str]:
    """Return a list of validation errors (empty = valid)."""
    errors = []

    if not config.get("secret"):
        errors.append("'secret' is required (use ${ENV_VAR} for env expansion)")

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

    return errors
