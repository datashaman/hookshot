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


def expand_template(
    template: str,
    payload: dict,
    state_context: dict | None = None,
) -> str:
    """Replace ${{ dotpath }} placeholders with values from the payload.

    Paths starting with "state." resolve from state_context instead.
    """
    def replacer(m):
        path = m.group(1).strip()
        if path.startswith("state.") and state_context is not None:
            state_key = path[len("state."):]
            return state_context.get(state_key, "")
        return resolve_dotpath(payload, path)

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

    # Check condition
    if "if" in cmd_config:
        condition = expand_template(str(cmd_config["if"]), payload, state_context)
        if not is_truthy(condition):
            log.info("  Skipped (condition false): %s", command)
            return False

    if dry_run:
        log.info("  [dry-run] Would execute: %s", command)
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
        )
        if result.stdout:
            log.info("  stdout: %s", result.stdout.rstrip())
        if result.stderr:
            log.warning("  stderr: %s", result.stderr.rstrip())
        if result.returncode != 0:
            log.error("  Exit code: %d", result.returncode)
            return True

        # Store/clear only on success (exit code 0)
        _process_store(cmd_config, payload, state, state_context)
        _process_clear(cmd_config, payload, state)

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
