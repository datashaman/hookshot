"""Template expansion and command execution."""

from __future__ import annotations

import logging
import re
import subprocess
from typing import TYPE_CHECKING

from .config import DEFAULT_COMMAND_TIMEOUT
from .reactions import add_reaction, remove_reaction

if TYPE_CHECKING:
    from .state import StateStore

log = logging.getLogger("hookshot")


def _to_string(value: object) -> str:
    """Convert a resolved value to its string representation."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def resolve_dotpath(payload: dict, path: str) -> str | list:
    """Resolve a dot-separated path into a JSON payload.

    Supports wildcard notation: ``issue.labels.*.name`` extracts the
    ``name`` field from each element when the preceding segment is a list.

    Returns a list when a wildcard is used, otherwise a string (or empty
    string if the path is not found).
    """
    current: object = payload
    for key in path.split("."):
        if key == "*":
            if not isinstance(current, list):
                return ""
            # Remaining keys after "*" will be resolved per element
            continue
        if isinstance(current, list):
            # We're iterating after a "*": extract `key` from each element
            extracted = []
            for item in current:
                if isinstance(item, dict) and key in item:
                    extracted.append(item[key])
            current = extracted
        elif isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return ""

    if isinstance(current, list):
        return [_to_string(v) for v in current]
    return _to_string(current)


def apply_filter(value: str | list, filter_expr: str) -> str:
    """Apply a pipe filter to a resolved value.

    Supported filters:
        contains <arg>      → "true" if value contains arg (case-insensitive)
        not_contains <arg>  → "true" if value does NOT contain arg (case-insensitive)
        eq <arg>            → "true" if value equals arg (case-insensitive)
        neq <arg>           → "true" if value does NOT equal arg (case-insensitive)
        lower               → lowercase
        upper               → uppercase
        any <arg>           → "true" if any element in a list equals arg (case-insensitive)
        none <arg>          → "true" if no element in a list equals arg (case-insensitive)
    """
    parts = filter_expr.strip().split(None, 1)
    name = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    if name == "any":
        if isinstance(value, list):
            return "true" if any(v.lower() == arg.lower() for v in value) else "false"
        return "true" if value.lower() == arg.lower() else "false"
    elif name == "none":
        if isinstance(value, list):
            return "true" if not any(v.lower() == arg.lower() for v in value) else "false"
        return "true" if value.lower() != arg.lower() else "false"

    # String-only filters: stringify lists for backwards compatibility
    if isinstance(value, list):
        value = str(value)

    if name == "contains":
        return "true" if arg.lower() in value.lower() else "false"
    elif name == "not_contains":
        return "true" if arg.lower() not in value.lower() else "false"
    elif name == "eq":
        return "true" if value.strip().lower() == arg.lower() else "false"
    elif name == "neq":
        return "true" if value.strip().lower() != arg.lower() else "false"
    elif name == "lower":
        return value.lower()
    elif name == "upper":
        return value.upper()
    else:
        log.warning("Unknown filter: %s", name)
        return value


def expand_template(
    template: str,
    payload: dict,
    state_context: dict | None = None,
) -> str:
    """Replace ${{ dotpath }} or ${{ dotpath | filter arg }} placeholders.

    Paths starting with "state." resolve from state_context instead.
    Pipe filters are applied after value resolution.
    """
    def replacer(m: re.Match[str]) -> str:
        expr = m.group(1).strip()

        # Split on first pipe to separate path from filter
        if "|" in expr:
            path, filter_expr = expr.split("|", 1)
            path = path.strip()
        else:
            path = expr
            filter_expr = None

        # Resolve value (may be str or list when wildcards are used)
        if path.startswith("state.") and state_context is not None:
            state_key = path[len("state."):]
            resolved: str | list[str] = str(state_context.get(state_key, ""))
        else:
            resolved = resolve_dotpath(payload, path)

        # Apply filter if present
        if filter_expr:
            return apply_filter(resolved, filter_expr)

        # No filter — stringify for substitution
        if isinstance(resolved, list):
            return str(resolved)
        return resolved

    return re.sub(r"\$\{\{\s*([^}]+?)\s*\}\}", replacer, template)


def resolve_command_timeout(cmd_config: dict, default_timeout: int | None) -> int:
    """Per-command timeout overrides global default; else fallback seconds."""
    if "timeout" in cmd_config:
        return cmd_config["timeout"]
    if default_timeout is not None:
        return default_timeout
    return DEFAULT_COMMAND_TIMEOUT


def is_truthy(value: str) -> bool:
    """Evaluate a string for truthiness after template expansion.

    Falsy: empty string, "false", "False", "null", "None", "0"
    Everything else is truthy.
    """
    return value.strip().lower() not in ("", "false", "null", "none", "0")


def run_command(
    cmd_config: dict,
    payload: dict,
    *,
    dry_run: bool = False,
    state: StateStore | None = None,
    reactions: dict | None = None,
    cwd: str | None = None,
    default_timeout: int | None = None,
) -> bool:
    """Expand templates in a command config and execute it.

    Returns True if the command ran (or would run in dry_run mode).

    default_timeout: seconds when the command has no ``timeout`` key (from global
        config). Falls back to :data:`hookshot.config.DEFAULT_COMMAND_TIMEOUT`.
    """
    # Load state context
    state_context = None
    if "load" in cmd_config and state is not None:
        load_key = expand_template(cmd_config["load"]["key"], payload)
        state_context = state.get_context(load_key)
        log.info("  Loaded state: %s", load_key)

    command = expand_template(cmd_config["command"], payload, state_context)

    # Expand optional stdin content
    stdin_text = None
    if "stdin" in cmd_config:
        stdin_text = expand_template(str(cmd_config["stdin"]), payload, state_context)

    # Check conditions — single string or list (all must be truthy)
    if "if" in cmd_config:
        conditions = cmd_config["if"]
        if isinstance(conditions, str):
            conditions = [conditions]
        for cond in conditions:
            expanded = expand_template(str(cond), payload, state_context)
            if not is_truthy(expanded):
                log.info("  Skipped (condition false: %s): %s", cond, command)
                return False

    timeout_sec = resolve_command_timeout(cmd_config, default_timeout)

    if dry_run:
        log.info("  [dry-run] Would execute: %s", command)
        if cwd:
            log.info("  [dry-run] cwd: %s", cwd)
        log.info("  [dry-run] timeout: %ds", timeout_sec)
        if stdin_text:
            log.info("  [dry-run] stdin: %s", stdin_text[:200])
        _process_store(cmd_config, payload, state, state_context, dry_run=True)
        _process_clear(cmd_config, payload, state, dry_run=True)
        return True

    log.info("  Executing: %s", command)
    if cwd:
        log.info("  cwd: %s", cwd)

    # Add "working" reaction before execution
    working_reaction = reactions.get("working") if reactions else None
    if working_reaction:
        add_reaction(payload, working_reaction)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            input=stdin_text,
            cwd=cwd,
        )
        if result.stdout:
            log.info("  stdout: %s", result.stdout.rstrip())
        if result.stderr:
            log.warning("  stderr: %s", result.stderr.rstrip())
        if result.returncode != 0:
            log.error("  Command failed (exit code %d): %s", result.returncode, command)
            _finish_reactions(payload, reactions, success=False)
            return True

        # Store/clear only on success (exit code 0)
        log.info("  Command succeeded: %s", command)
        try:
            _process_store(cmd_config, payload, state, state_context)
        except Exception:
            store_key = cmd_config.get("store", {}).get("key", "?")
            log.error("  State store failed for key '%s'", store_key)
        try:
            _process_clear(cmd_config, payload, state)
        except Exception:
            clear_keys = cmd_config.get("clear", [])
            log.error("  State clear failed for keys %s", clear_keys)

        _finish_reactions(payload, reactions, success=True)
        return True
    except subprocess.TimeoutExpired:
        log.error("  Command timed out after %ds: %s", timeout_sec, command)
        _finish_reactions(payload, reactions, success=False)
        return False
    except Exception as e:
        log.error("  Command failed: %s", e)
        _finish_reactions(payload, reactions, success=False)
        return False


def _finish_reactions(
    payload: dict,
    reactions: dict | None,
    *,
    success: bool,
) -> None:
    """Remove the working reaction and add the done/failed reaction."""
    if not reactions:
        return

    working = reactions.get("working")
    if working:
        remove_reaction(payload, working)

    final = reactions.get("done") if success else reactions.get("failed")
    if final:
        add_reaction(payload, final)


def _process_store(
    cmd_config: dict,
    payload: dict,
    state: StateStore | None,
    state_context: dict | None = None,
    *,
    dry_run: bool = False,
):
    """Process the store directive on a command config."""
    if "store" not in cmd_config or state is None:
        return

    store_cfg = cmd_config["store"]
    key = expand_template(store_cfg["key"], payload, state_context)

    values = None
    if "values" in store_cfg:
        values = {
            k: expand_template(v, payload, state_context)
            for k, v in store_cfg["values"].items()
        }

    log_entry = None
    if "log" in store_cfg:
        log_entry = expand_template(store_cfg["log"], payload, state_context)

    if dry_run:
        if values:
            log.info("  [dry-run] Would store values at %s: %s", key, values)
        if log_entry:
            log.info("  [dry-run] Would append log at %s: %s", key, log_entry)
        return

    state.store(key, values, log_entry)


def _process_clear(
    cmd_config: dict,
    payload: dict,
    state: StateStore | None,
    *,
    dry_run: bool = False,
):
    """Process the clear directive on a command config."""
    if "clear" not in cmd_config or state is None:
        return

    for pattern_template in cmd_config["clear"]:
        pattern = expand_template(pattern_template, payload)
        if dry_run:
            log.info("  [dry-run] Would clear state: %s", pattern)
        else:
            state.delete(pattern)
