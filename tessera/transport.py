"""HTTP transport, behind a seam.

A connector never imports an HTTP library. It asks a transport to make a request
and gets a `Response` back, or a taxonomy error. That seam is what makes a
connector testable without a tenant, a token or a network: the test supplies a
transport that returns recorded shapes.

`HttpTransport` uses the standard library. `RecordedTransport` replays fixtures
and records what was asked for.

Nothing here runs at import time and nothing reaches the network unless a
connector is constructed with `HttpTransport` and actually called.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from .connector import AuthError, ContractError, RateLimited, TransientError


@dataclass
class Response:
    status: int
    body: object = None
    headers: dict = field(default_factory=dict)
    url: str = ""

    def json(self):
        return self.body


class Transport:
    """The seam."""

    def request(self, method: str, url: str, *, headers: dict | None = None,
                params: dict | None = None, json_body: dict | None = None) -> Response:
        raise NotImplementedError


def classify(status: int, body, headers: dict | None = None) -> Response:
    """Map an HTTP status onto the connector error taxonomy.

    This mapping is the reason the taxonomy is closed: every provider fails in
    the same six ways, and a caller should not have to learn a seventh.
    """
    headers = headers or {}
    if 200 <= status < 300:
        return Response(status=status, body=body, headers=headers)
    if status in (401, 403):
        raise AuthError(f"credentials rejected ({status})")
    if status == 429:
        retry_after = float(headers.get("Retry-After", 1.0) or 1.0)
        raise RateLimited(f"throttled ({status})", retry_after=retry_after)
    if status >= 500:
        raise TransientError(f"server error ({status})")
    raise ContractError(f"request rejected ({status})")


class HttpTransport(Transport):
    """Standard-library HTTP. No dependencies, no retries of its own."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def request(self, method: str, url: str, *, headers: dict | None = None,
                params: dict | None = None, json_body: dict | None = None) -> Response:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        data = None
        all_headers = dict(headers or {})
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            all_headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=data, headers=all_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                body = json.loads(raw) if raw else None
                return classify(resp.status, body, dict(resp.headers))
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                body = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                body = None
            return classify(exc.code, body, dict(exc.headers or {}))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TransientError(f"transport failure: {exc}") from exc


class RecordedTransport(Transport):
    """Replays a handler. Used by the tests, and by anyone proving a connector.

    `handler(method, url, params, json_body) -> Response` (or raises). Every
    request is appended to `calls`, so a test can assert what was actually sent
    rather than only what came back.
    """

    def __init__(self, handler):
        self.handler = handler
        self.calls: list[dict] = []

    def request(self, method: str, url: str, *, headers: dict | None = None,
                params: dict | None = None, json_body: dict | None = None) -> Response:
        self.calls.append({
            "method": method, "url": url, "params": dict(params or {}),
            "body": json_body, "headers": dict(headers or {}),
        })
        response = self.handler(method, url, params or {}, json_body)
        # Apply the same status mapping the real transport applies, so a fixture
        # that returns 401 exercises the same code path a live tenant would.
        return classify(response.status, response.body, response.headers)

    def last(self) -> dict:
        return self.calls[-1]
