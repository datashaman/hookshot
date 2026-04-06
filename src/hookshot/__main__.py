"""CLI entry point for hookshot."""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

import yaml

from .config import LOCAL_CONFIG_PATH, get_events, load_config, validate_config
from .matcher import match_and_run
from .server import serve
from .state import StateStore


def main():
    parser = argparse.ArgumentParser(
        prog="hookshot",
        description="GitHub webhook receiver that runs shell commands from a YAML config",
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=None,
        help="Path to config (default: ./hookshot.yml, then ~/.config/hookshot/hooks.yml)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    sub = parser.add_subparsers(dest="command")

    # serve
    sub.add_parser("serve", help="Start the webhook server")

    # validate
    sub.add_parser("validate", help="Validate the config file")

    # test
    test_parser = sub.add_parser("test", help="Simulate a webhook event")
    test_parser.add_argument("event", help="Event name (e.g. push, pull_request.closed)")
    test_parser.add_argument(
        "payload",
        help="JSON payload as string or @filename",
    )

    # init
    sub.add_parser("init", help="Create a starter hookshot.yml config")

    # state
    state_parser = sub.add_parser("state", help="Inspect and manage state")
    state_sub = state_parser.add_subparsers(dest="state_command")

    state_sub.add_parser("list", help="List all state keys")

    state_get_parser = state_sub.add_parser("get", help="Get a state bucket")
    state_get_parser.add_argument("key", help="State key to retrieve")

    state_clear_parser = state_sub.add_parser("clear", help="Clear state keys")
    state_clear_parser.add_argument("pattern", help="Key or pattern (supports * suffix)")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_format = "%(asctime)s %(levelname)s %(message)s"

    logging.basicConfig(
        format=log_format,
        level=log_level,
    )

    # Also log to hookshot.log for persistent review
    file_handler = logging.FileHandler("hookshot.log")
    file_handler.setFormatter(logging.Formatter(log_format))
    file_handler.setLevel(log_level)
    logging.getLogger("hookshot").addHandler(file_handler)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "validate":
        cmd_validate(args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "test":
        cmd_test(args)
    elif args.command == "init":
        cmd_init(args)
    elif args.command == "state":
        cmd_state(args)


def _detect_repo() -> str | None:
    """Try to detect owner/repo from git remote."""
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def cmd_init(args):
    config_path = args.config or LOCAL_CONFIG_PATH

    if config_path.exists():
        print(f"Config already exists: {config_path}", file=sys.stderr)
        sys.exit(1)

    repo = _detect_repo()
    if repo:
        print(f"Detected repo: {repo}")
    else:
        print("Could not detect repo from git remote.")
        repo = input("Enter repo (owner/name): ").strip()
        if not repo:
            print("Aborted.", file=sys.stderr)
            sys.exit(1)

    config = {
        "repo": repo,
        "hooks": {
            "issues.opened": [
                {"command": "echo 'New issue #${{ issue.number }}: ${{ issue.title }}'"}
            ],
            "push": [
                {"command": "echo 'Push to ${{ repository.full_name }} on ${{ ref }}'"}
            ],
        },
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"Created {config_path}")
    print("Edit the hooks to match your needs, then run: hookshot serve")


def cmd_validate(args):
    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    errors = validate_config(config)
    if errors:
        print("Config validation failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    hooks = config.get("hooks", {})
    total_commands = sum(len(cmds) for cmds in hooks.values())
    print(f"Config OK: {len(hooks)} hook(s), {total_commands} command(s)")

    repo = config.get("repo")
    if repo:
        events = get_events(config)
        print(f"Repo: {repo}")
        print(f"GitHub events: {', '.join(events)}")

    for event, cmds in hooks.items():
        for cmd in cmds:
            condition = f" (if: {cmd['if']})" if "if" in cmd else ""
            print(f"  {event}: {cmd['command']}{condition}")


def cmd_serve(args):
    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    errors = validate_config(config)
    if errors:
        print("Config validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    serve(config)


def cmd_test(args):
    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse payload
    payload_str = args.payload
    if payload_str.startswith("@"):
        path = Path(payload_str[1:])
        if not path.exists():
            print(f"Error: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        payload_str = path.read_text()

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Split qualified event name for matching
    event = args.event
    if "." in event:
        base_event, action = event.split(".", 1)
        payload.setdefault("action", action)
        event = base_event

    state = StateStore(config.get("state_file"))
    hooks = config.get("hooks", {})
    worktrees = config.get("worktrees")
    executed = match_and_run(
        hooks,
        event,
        payload,
        dry_run=True,
        state=state,
        worktrees=worktrees,
        default_timeout=config.get("timeout"),
    )
    print(f"\nMatched and would execute {executed} command(s)")


def cmd_state(args):
    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    store = StateStore(config.get("state_file"))

    if args.state_command is None:
        print("Usage: hookshot state {list,get,clear}", file=sys.stderr)
        sys.exit(1)

    if args.state_command == "list":
        keys = store.keys()
        if not keys:
            print("(no state)")
            return
        for key in keys:
            bucket = store.get(key)
            n_values = len(bucket.get("values", {}))
            n_log = len(bucket.get("log", []))
            print(f"  {key}  ({n_values} values, {n_log} log entries)")

    elif args.state_command == "get":
        bucket = store.get(args.key)
        if not bucket.get("values") and not bucket.get("log"):
            print(f"No state for key: {args.key}")
            return
        if bucket.get("values"):
            print("Values:")
            for k, v in bucket["values"].items():
                print(f"  {k}: {v}")
        if bucket.get("log"):
            print("Log:")
            for entry in bucket["log"]:
                print(f"  - {entry}")

    elif args.state_command == "clear":
        store.delete(args.pattern)
        print(f"Cleared: {args.pattern}")


if __name__ == "__main__":
    main()
