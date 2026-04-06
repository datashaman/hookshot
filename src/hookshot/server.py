"""HTTP webhook server with HMAC-SHA256 verification."""

import hashlib
import hmac
import json
import logging
import shutil
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

from .config import get_events
from .matcher import match_and_run
from .state import StateStore

log = logging.getLogger("hookshot")


class WebhookHandler(BaseHTTPRequestHandler):
    """Handle incoming GitHub webhook POST requests."""

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Verify signature (only when not using gh webhook forward)
        secret = self.server.hookshot_config.get("secret")
        if secret:
            signature = self.headers.get("X-Hub-Signature-256", "")
            if not verify_signature(body, secret, signature):
                log.warning("Invalid signature from %s", self.client_address[0])
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Invalid signature")
                return

        # Parse event
        event = self.headers.get("X-GitHub-Event", "")
        if not event:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing X-GitHub-Event header")
            return

        # Handle ping
        if event == "ping":
            log.info("Received ping from GitHub")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"pong")
            return

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            log.error("Invalid JSON payload: %s", e)
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid JSON")
            return

        log.info("Received event: %s (action: %s)", event, payload.get("action", "-"))

        hooks = self.server.hookshot_config.get("hooks", {})
        executed = match_and_run(hooks, event, payload, state=self.server.hookshot_state)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(f"Executed {executed} command(s)".encode())

    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"hookshot ok")

    def log_message(self, format, *args):
        """Route HTTP server logs through our logger."""
        log.debug(format, *args)


def verify_signature(body: bytes, secret: str, signature: str) -> bool:
    """Verify the HMAC-SHA256 signature from GitHub."""
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def serve(config: dict):
    """Start the webhook server, optionally with gh webhook forwarding."""
    host = config["listen"]["host"]
    port = config["listen"]["port"]
    repo = config.get("repo")

    server = HTTPServer((host, port), WebhookHandler)
    server.hookshot_config = config
    server.hookshot_state = StateStore(config.get("state_file"))

    log.info("Hookshot listening on %s:%d", host, port)
    log.info("Configured hooks: %s", ", ".join(config.get("hooks", {}).keys()) or "(none)")
    log.info("State file: %s", server.hookshot_state.path)

    gh_proc = None
    if repo:
        gh_proc = _start_gh_forward(config, port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")
    finally:
        if gh_proc:
            log.info("Stopping gh webhook forward")
            gh_proc.terminate()
            gh_proc.wait()
        server.server_close()


def _ensure_gh_webhook_extension():
    """Check that gh CLI and its webhook extension are available."""
    if not shutil.which("gh"):
        raise RuntimeError(
            "gh CLI not found. Install it from https://cli.github.com/ "
            "or remove 'repo' from config to use direct webhooks."
        )

    # Check if the webhook extension is installed
    result = subprocess.run(
        ["gh", "extension", "list"],
        capture_output=True, text=True,
    )
    if "webhook" not in result.stdout:
        log.info("Installing gh webhook extension...")
        install = subprocess.run(
            ["gh", "extension", "install", "cli/gh-webhook"],
            capture_output=True, text=True,
        )
        if install.returncode != 0:
            raise RuntimeError(
                f"Failed to install gh webhook extension: {install.stderr.strip()}"
            )
        log.info("gh webhook extension installed")


def _start_gh_forward(config: dict, port: int) -> subprocess.Popen:
    """Spawn gh webhook forward to receive events from GitHub."""
    _ensure_gh_webhook_extension()

    repo = config["repo"]
    events = get_events(config)

    if not events:
        raise RuntimeError("No events to subscribe to — add hooks to your config.")

    cmd = [
        "gh", "webhook", "forward",
        f"--repo={repo}",
        f"--events={','.join(events)}",
        f"--url=http://localhost:{port}",
    ]

    # Add secret if configured
    secret = config.get("secret")
    if secret:
        cmd.append(f"--secret={secret}")

    log.info("Starting: %s", " ".join(cmd))
    log.info("Forwarding events: %s", ", ".join(events))

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    return proc
