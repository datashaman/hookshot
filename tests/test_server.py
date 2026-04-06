"""Tests for webhook server background processing."""

from io import BytesIO
from unittest.mock import MagicMock, patch

from hookshot.server import HookshotHTTPServer, WebhookHandler, _run_webhook_commands


def _make_handler(headers: dict, body: bytes):
    """Build a WebhookHandler without running the real HTTP stack."""
    server = MagicMock(spec=HookshotHTTPServer)
    server.hookshot_config = {
        "hooks": {"issues": [{"command": "echo x"}]},
        "reactions": None,
        "worktrees": None,
        "timeout": None,
    }
    server.hookshot_state = MagicMock()
    server.hookshot_work_seq = iter(range(1, 1000))
    server.hookshot_executor = MagicMock()

    handler = WebhookHandler.__new__(WebhookHandler)
    handler.server = server
    handler.client_address = ("127.0.0.1", 12345)
    handler.rfile = BytesIO(body)
    handler.wfile = BytesIO()
    handler.headers = headers

    def _send_response_only(code, message=None):
        handler._response_code = code

    def _send_header(k, v):
        pass

    def _end_headers():
        pass

    handler.send_response = _send_response_only
    handler.send_header = _send_header
    handler.end_headers = _end_headers

    return handler, server


def test_post_queues_work_and_returns_202():
    headers = {
        "Content-Length": "20",
        "X-GitHub-Event": "issues",
        "X-GitHub-Delivery": "abc-123",
    }
    body = b'{"action":"opened"}'
    handler, server = _make_handler(headers, body)

    handler.do_POST()

    assert getattr(handler, "_response_code", None) == 202
    raw = handler.wfile.getvalue()
    assert b"Accepted" in raw
    assert b"work 1" in raw
    assert b"abc-123" in raw
    server.hookshot_executor.submit.assert_called_once()
    args, kwargs = server.hookshot_executor.submit.call_args
    assert args[0] is _run_webhook_commands
    assert args[2] == 1  # work_id
    assert args[3] == "abc-123"  # delivery


@patch("hookshot.server.match_and_run", return_value=2)
def test_run_webhook_commands_invokes_matcher(mock_match):
    server = MagicMock()
    server.hookshot_state = MagicMock()
    _run_webhook_commands(
        server,
        7,
        "del-1",
        "issues",
        {"action": "opened"},
        {"issues": [{"command": "echo"}]},
        None,
        None,
        300,
    )
    mock_match.assert_called_once()
    call = mock_match.call_args
    assert call[0][0] == {"issues": [{"command": "echo"}]}
    assert call[0][1] == "issues"
    assert call[0][2] == {"action": "opened"}
    assert call[1]["state"] is server.hookshot_state
    assert call[1]["default_timeout"] == 300


@patch("hookshot.server.match_and_run", side_effect=RuntimeError("boom"))
def test_run_webhook_commands_swallows_and_logs(mock_match, caplog):
    import logging

    caplog.set_level(logging.ERROR)
    server = MagicMock()
    server.hookshot_state = MagicMock()
    _run_webhook_commands(
        server,
        1,
        "d",
        "push",
        {},
        {},
        None,
        None,
        None,
    )
    assert "boom" in caplog.text


def test_hookshot_server_has_executor():
    # bind_and_activate=False avoids binding a real port in tests
    srv = HookshotHTTPServer(
        ("127.0.0.1", 0),
        WebhookHandler,
        bind_and_activate=False,
    )
    assert srv.hookshot_executor is not None
    assert next(srv.hookshot_work_seq) == 1
    assert next(srv.hookshot_work_seq) == 2
    srv.hookshot_executor.shutdown(wait=False)
