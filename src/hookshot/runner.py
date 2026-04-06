"""Template expansion and command execution."""

import logging
import re
import subprocess

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


def expand_template(template: str, payload: dict) -> str:
    """Replace ${{ dotpath }} placeholders with values from the payload."""
    return re.sub(
        r"\$\{\{\s*([^}]+?)\s*\}\}",
        lambda m: resolve_dotpath(payload, m.group(1).strip()),
        template,
    )


def is_truthy(value: str) -> bool:
    """Evaluate a string for truthiness after template expansion.

    Falsy: empty string, "false", "False", "null", "None", "0"
    Everything else is truthy.
    """
    return value.strip().lower() not in ("", "false", "null", "none", "0")


def run_command(cmd_config: dict, payload: dict, *, dry_run: bool = False) -> bool:
    """Expand templates in a command config and execute it.

    Returns True if the command ran (or would run in dry_run mode).
    """
    command = expand_template(cmd_config["command"], payload)

    # Check condition
    if "if" in cmd_config:
        condition = expand_template(str(cmd_config["if"]), payload)
        if not is_truthy(condition):
            log.info("  Skipped (condition false): %s", command)
            return False

    if dry_run:
        log.info("  [dry-run] Would execute: %s", command)
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
    except subprocess.TimeoutExpired:
        log.error("  Command timed out after 300s: %s", command)
        return False
    except Exception as e:
        log.error("  Command failed: %s", e)
        return False
