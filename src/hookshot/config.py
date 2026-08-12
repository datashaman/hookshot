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
DIST_CONFIG_PATH = Path("hookshot.dist.yml")
DEFAULT_CONFIG_PATH = _CONFIG_DIR / "hooks.yml"
DEFAULT_STATE_PATH = _DATA_DIR / "state.json"
DOTENV_PATH = Path(".env")

# Fallback when neither global nor per-command timeout is set (seconds)
DEFAULT_COMMAND_TIMEOUT = 300


def load_dotenv(path: Path = DOTENV_PATH) -> None:
    """Load KEY=VALUE pairs from a .env file into the process environment.

    Mirrors common dotenv tooling: blank lines and '#' comments are skipped,
    a leading 'export ' is stripped, and values may be wrapped in matching
    single or double quotes. A variable already set in the process
    environment is left untouched — .env only supplies defaults, so
    `CLAUDE_BIN=... hookshot serve` still overrides it. No-op if the file
    doesn't exist.
    """
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]

        if key and key not in os.environ:
            os.environ[key] = value


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
    """Find the config file: ./hookshot.yml, then ./hookshot.dist.yml, then global default.

    Mirrors phpunit.xml / phpunit.xml.dist: a team commits hookshot.dist.yml as the
    shared baseline, and a local hookshot.yml (typically gitignored) overrides it.
    """
    if LOCAL_CONFIG_PATH.exists():
        return LOCAL_CONFIG_PATH
    if DIST_CONFIG_PATH.exists():
        return DIST_CONFIG_PATH
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

    # Normalize the env block: coerce to strings, expand ${VAR} in values so
    # declared defaults can compose with the process environment.
    env_block = config.get("env") or {}
    if isinstance(env_block, dict):
        config["env"] = {
            str(key): expand_env(str(value)) for key, value in env_block.items()
        }
    else:
        config["env"] = {}

    _resolve_agents(config)

    return config


def resolved_env(config: dict) -> dict[str, str]:
    """Merge the declared ``env`` block with the process environment.

    The process environment wins: a var exported at run time overrides the
    config's declared default, so ``CLAUDE_BIN=... hookshot serve`` works
    without editing the config.
    """
    return {**config.get("env", {}), **os.environ}


# Matches ${{ env.NAME }} (with optional filter) inside a template string.
_ENV_REF_RE = re.compile(r"\$\{\{\s*env\.([A-Za-z_][A-Za-z0-9_]*)")


def unresolved_env_refs(config: dict) -> list[str]:
    """Return sorted names referenced via ${{ env.X }} that resolve to nothing.

    A name is "unresolved" if it is neither declared in the config's ``env``
    block nor set in the process environment. This is advisory only — used to
    warn, not to fail validation, since it depends on the ambient environment.
    """
    declared = config.get("env", {})
    strings: list[str] = []

    for commands in config.get("hooks", {}).values():
        if not isinstance(commands, list):
            continue
        for cmd in commands:
            if not isinstance(cmd, dict):
                continue
            for key in ("command", "stdin"):
                if key in cmd:
                    strings.append(str(cmd[key]))
            if "if" in cmd:
                conditions = cmd["if"]
                if isinstance(conditions, str):
                    conditions = [conditions]
                strings.extend(str(c) for c in conditions)
            if "load" in cmd and isinstance(cmd["load"], dict) and "key" in cmd["load"]:
                strings.append(str(cmd["load"]["key"]))
            if "store" in cmd and isinstance(cmd["store"], dict):
                store = cmd["store"]
                if "key" in store:
                    strings.append(str(store["key"]))
                if isinstance(store.get("values"), dict):
                    strings.extend(str(v) for v in store["values"].values())
                if "log" in store:
                    strings.append(str(store["log"]))
            if "clear" in cmd and isinstance(cmd["clear"], list):
                strings.extend(str(c) for c in cmd["clear"])

    names = set()
    for s in strings:
        names.update(_ENV_REF_RE.findall(s))

    unresolved = {name for name in names if name not in declared and name not in os.environ}
    return sorted(unresolved)


def _resolve_agents(config: dict):
    """Expand agent references in hooks to full command/stdin definitions.

    If a hook has `agent: <name>`, the agent's `command` is copied in and
    the hook's `stdin` (if any) is appended to the agent's base `stdin`.
    """
    agents = config.get("agents", {})

    for event, commands in config.get("hooks", {}).items():
        for i, cmd in enumerate(commands):
            if "agent" not in cmd:
                continue
            agent_name = cmd["agent"]
            if agent_name not in agents:
                raise ValueError(
                    f"hooks.{event}[{i}]: references undefined agent '{agent_name}'"
                )
            if "command" in cmd:
                raise ValueError(
                    f"hooks.{event}[{i}]: cannot have both 'agent' and 'command'"
                )
            agent_def = agents[agent_name]
            cmd["command"] = agent_def["command"]

            # Append hook stdin to agent base stdin
            base_stdin = agent_def.get("stdin", "")
            hook_stdin = cmd.get("stdin", "")
            if base_stdin and hook_stdin:
                cmd["stdin"] = base_stdin.rstrip("\n") + "\n" + hook_stdin
            elif base_stdin:
                cmd["stdin"] = base_stdin
            # else hook_stdin stays as-is (or absent)

            del cmd["agent"]


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

            if "stream" in cmd and not isinstance(cmd["stream"], bool):
                errors.append(f"hooks.{event}[{i}].stream: must be a boolean")

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

    # Validate env
    env_block = config.get("env")
    if env_block is not None and env_block != {}:
        if not isinstance(env_block, dict):
            errors.append("'env' must be a mapping")
        else:
            for key, value in env_block.items():
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", str(key)):
                    errors.append(f"env.{key}: invalid name (must match [A-Za-z_][A-Za-z0-9_]*)")
                if isinstance(value, (dict, list)):
                    errors.append(f"env.{key}: value must be a scalar (string, number, or boolean)")

    # Validate agents
    agents = config.get("agents")
    if agents is not None:
        if not isinstance(agents, dict):
            errors.append("'agents' must be a mapping")
        else:
            for name, defn in agents.items():
                if not isinstance(defn, dict):
                    errors.append(f"agents.{name}: must be a mapping")
                    continue
                if "command" not in defn:
                    errors.append(f"agents.{name}: missing 'command' key")
                valid_agent_keys = {"command", "stdin"}
                for key in defn:
                    if key not in valid_agent_keys:
                        errors.append(
                            f"agents.{name}.{key}: unknown key (expected: command, stdin)"
                        )

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

    # Validate notify_on_failure
    if "notify_on_failure" in config and not isinstance(config["notify_on_failure"], bool):
        errors.append("'notify_on_failure' must be a boolean")

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
