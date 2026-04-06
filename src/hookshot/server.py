"""HTTP webhook server with HMAC-SHA256 verification."""

import hashlib
import hmac
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

from .matcher import match_and_run

log = logging.getLogger("hookshot")


class WebhookHandler(BaseHTTPRequestHandler):
    """Handle incoming GitHub webhook POST requests."""

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Verify signature
        secret = self.server.hookshot_config["secret"]
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
        executed = match_and_run(hooks, event, payload)

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
    """Start the webhook server."""
    host = config["listen"]["host"]
    port = config["listen"]["port"]

    server = HTTPServer((host, port), WebhookHandler)
    server.hookshot_config = config

    log.info("Hookshot listening on %s:%d", host, port)
    log.info("Configured hooks: %s", ", ".join(config.get("hooks", {}).keys()) or "(none)")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")
        server.server_close()
