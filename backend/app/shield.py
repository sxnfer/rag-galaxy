"""
Three small guards that sit in front of every request to the public API.

guard.py limits the questions that cost money. These limit everything else, so
the free calls can't be used to wear the server down:

  BodyLimit        a request's message may only be a few kilobytes. A question
                   is at most 300 characters, so anything bigger is not a question.
  RequestRate      each visitor may make only so many requests a minute, of any kind.
  SecurityHeaders  every reply tells the browser to be strict with it.

Each is a piece of "middleware": code every request passes through on its way
in, and every reply passes through on its way out.
"""

import json
import time

from .guard import _env_int, visitor_id

MAX_BODY_BYTES = _env_int("MAX_BODY_BYTES", 8192)             # a 300-character question is under 2 KB as JSON
REQUESTS_PER_MINUTE = _env_int("REQUESTS_PER_MINUTE", 120)    # one page load is 3 requests


async def _reject(send, status: int, detail: str, headers: dict[str, str] | None = None) -> None:
    """Reply with a short JSON message, in the same shape as the API's other errors."""
    body = json.dumps({"detail": detail}).encode()
    extra = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), *extra]})
    await send({"type": "http.response.body", "body": body})


class _TooLarge(Exception):
    pass


class BodyLimit:
    """Refuse a request whose message is bigger than max_bytes, without reading it all into memory first."""

    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self.max_bytes:
            return await _reject(send, 413, "That message is too large.")

        # A sender doesn't have to say how big its message is, so count what actually arrives too.
        seen = 0

        async def counted():
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max_bytes:
                    raise _TooLarge
            return message

        try:
            await self.app(scope, counted, send)
        except _TooLarge:
            await _reject(send, 413, "That message is too large.")


class RequestRate:
    """At most per_minute requests a minute from one visitor, whatever they ask for.

    Counted in memory, in one-minute windows: when the minute changes, everyone starts again.
    """

    def __init__(self, app, per_minute: int = REQUESTS_PER_MINUTE, clock=time.time) -> None:
        self.app, self.per_minute, self.clock = app, per_minute, clock
        self.minute, self.counts = -1, {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        now = self.clock()
        minute = int(now // 60)
        if minute != self.minute:
            self.minute, self.counts = minute, {}
        peer = scope["client"][0] if scope.get("client") else None
        forwarded = dict(scope["headers"]).get(b"x-forwarded-for")
        visitor = visitor_id(peer, forwarded.decode("latin-1") if forwarded else None)
        self.counts[visitor] = self.counts.get(visitor, 0) + 1
        if self.counts[visitor] > self.per_minute:
            wait = max(1, int(60 - now % 60))
            return await _reject(send, 429, "Too many requests. Please wait a moment.", {"Retry-After": str(wait)})
        await self.app(scope, receive, send)


class SecurityHeaders:
    """Add a few standard instructions for the browser to every reply."""

    HEADERS = [
        (b"x-content-type-options", b"nosniff"),                                    # don't guess what kind of file a reply is
        (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),     # always use https for this address
        (b"referrer-policy", b"no-referrer"),
        (b"x-frame-options", b"DENY"),                                              # never show this API inside another page
    ]

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def with_headers(message):
            if message["type"] == "http.response.start":
                message = {**message, "headers": [*message.get("headers", []), *self.HEADERS]}
            await send(message)

        await self.app(scope, receive, with_headers)
