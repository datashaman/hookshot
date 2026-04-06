"""Template expansion and command execution."""

from __future__ import annotations

import logging
import re
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import StateStore

log = logging.getLogger("hookshot")


def resolve_dotpath(payload: dict, path: str) -> str:
    """Resolve a dot-separated path into a JSON payload.

    Returns the value as a string, or empty string if not found.
    """
    current = payload
    for key in path.split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return ""
    if current is None:
        return ""
    if isinstance(current, bool):
        return "true" if current else "false"
    return str(current)


def apply_filter(value: str, filter_expr: str) -> str:
    """Apply a pipe filter to a resolved value.

    Supported filters:
        contains <arg>      → "true" if value contains arg (case-insensitive)
        not_contains <arg>  → "true" if value does NOT contain arg (case-insensitive)
        eq <arg>            → "true" if value equals arg (case-insensitive)
        neq <arg>           → "true" if value does NOT equal arg (case-insensitive)
        lower               → lowercase
        upper               → uppercase
    """
    parts = filter_expr.strip().split(None, 1)
    name = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

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
    def replacer(m):
        expr = m.group(1).strip()

        # Split on first pipe to separate path from filter
        if "|" in expr:
            path, filter_expr = expr.split("|", 1)
            path = path.strip()
        else:
            path = expr
            filter_expr = None

        # Resolve value
        if path.startswith("state.") and state_context is not None:
            state_key = path[len("state."):]
            value = state_context.get(state_key, "")
        else:
            value = resolve_dotpath(payload, path)

        # Apply filter if present
        if filter_expr:
            value = apply_filter(value, filter_expr)

        return value

    return re.sub(r"\$\{\{\s*([^}]+?)\s*\}\}", replacer, template)


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
) -> bool:
    """Expand templates in a command config and execute it.

    Returns True if the command ran (or would run in dry_run mode).
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

    if dry_run:
        log.info("  [dry-run] Would execute: %s", command)
        if stdin_text:
            log.info("  [dry-run] stdin: %s", stdin_text[:200])
        _process_store(cmd_config, payload, state, state_context, dry_run=True)
        _process_clear(cmd_config, payload, state, dry_run=True)
        return True

    log.info("  Executing: %s", command)
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
            input=stdin_text,
        )
        if result.stdout:
            log.info("  stdout: %s", result.stdout.rstrip())
        if result.stderr:
            log.warning("  stderr: %s", result.stderr.rstrip())
        if result.returncode != 0:
            log.error("  Command failed (exit code %d): %s", result.returncode, command)
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

        return True
    except subprocess.TimeoutExpired:
        log.error("  Command timed out after 300s: %s", command)
        return False
    except Exception as e:
        log.error("  Command failed: %s", e)
        return False


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
