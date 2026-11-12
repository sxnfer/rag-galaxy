"""The guards in front of every request (app/shield.py), tested without a server:
each is called the way the web server would call it, with a made-up request."""

import asyncio
import json

from app.shield import BodyLimit, RequestRate, SecurityHeaders


async def _ok(scope, receive, send):
    """A stand-in for the real app: reads the whole message, then says OK."""
    while (await receive()).get("more_body"):
        pass
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def call(app, headers=(), chunks=(b"",), client=("10.0.0.1", 1234)):
    """Send one request through `app`. Returns (status, headers, body)."""
    scope = {"type": "http", "method": "POST", "path": "/api/ask", "client": client,
             "headers": [(k.lower().encode(), v.encode()) for k, v in headers]}
    parts = list(chunks)
    sent = []

    async def receive():
        body = parts.pop(0)
        return {"type": "http.request", "body": body, "more_body": bool(parts)}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return start["status"], dict(start["headers"]), body


def test_small_message_passes():
    assert call(BodyLimit(_ok, max_bytes=100), chunks=(b"x" * 50,))[0] == 200


def test_message_that_says_it_is_too_big_is_refused_unread():
    status, _, body = call(BodyLimit(_ok, max_bytes=100), headers=[("Content-Length", "5000")], chunks=(b"x" * 5000,))
    assert status == 413 and "too large" in json.loads(body)["detail"]


def test_message_that_hides_its_size_is_cut_off():
    # No Content-Length: the size is only known as the pieces arrive.
    assert call(BodyLimit(_ok, max_bytes=100), chunks=(b"x" * 60, b"x" * 60))[0] == 413


def test_request_rate_per_visitor_and_new_minute():
    now = [0.0]
    app = RequestRate(_ok, per_minute=3, clock=lambda: now[0])
    assert [call(app)[0] for _ in range(4)] == [200, 200, 200, 429]
    assert call(app, client=("10.0.0.2", 1))[0] == 200  # another visitor is not affected
    now[0] += 60
    assert call(app)[0] == 200  # a new minute


def test_rate_limited_reply_says_when_to_retry():
    app = RequestRate(_ok, per_minute=0, clock=lambda: 10.0)
    status, headers, _ = call(app)
    assert status == 429 and headers[b"retry-after"] == b"50"


def test_security_headers_are_added():
    _, headers, _ = call(SecurityHeaders(_ok))
    assert headers[b"x-content-type-options"] == b"nosniff"
    assert b"max-age" in headers[b"strict-transport-security"]
