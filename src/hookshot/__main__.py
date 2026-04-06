"""CLI entry point for hookshot."""

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, load_config, validate_config
from .matcher import match_and_run
from .server import serve


def main():
    parser = argparse.ArgumentParser(
        prog="hookshot",
        description="GitHub webhook receiver that runs shell commands from a YAML config",
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to hooks.yml config (default: {DEFAULT_CONFIG_PATH})",
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

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "validate":
        cmd_validate(args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "test":
        cmd_test(args)


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

    hooks = config.get("hooks", {})
    executed = match_and_run(hooks, event, payload, dry_run=True)
    print(f"\nMatched and would execute {executed} command(s)")


if __name__ == "__main__":
    main()
