"""`EPIC-021J` — HTTP plumbing for the Binance-protocol fake server: parses
each request, dispatches to `spot_routes`/`futures_routes` by path prefix,
and owns the one piece of state (`OrderBookState`) both `GET
/fapi/v1/openOrders` and the order-lifecycle `POST`/`DELETE` routes share
for the lifetime of one `run_binance_fake_server()` call.

Any path/method this fixture does not recognize returns 404 rather than a
plausible-looking empty success — an unexpected call should be loud, not
silently swallowed. Responses are fixed and deterministic; nothing here
generates time-dependent or random data, which would reintroduce the
flakiness this tier exists to avoid.
"""

from __future__ import annotations

import gc
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl

from . import spot_routes
from .futures_routes import handle as handle_futures
from .order_book_state import OrderBookState


class _Handler(BaseHTTPRequestHandler):
    #: Set per-server-instance by `run_binance_fake_server()` via
    #: `HTTPServer`'s own `RequestHandlerClass` attribute-sharing —
    #: `BaseHTTPRequestHandler` is instantiated fresh per request, so state
    #: cannot live on `self`; it lives on the class, scoped by the
    #: contextmanager's own `try`/`finally` instead.
    order_book: OrderBookState

    def log_message(self, format: str, *args: object) -> None:
        pass  # Silence per-request access logs — this is a test fixture,
        # not a service anyone needs to watch run.

    def do_GET(self) -> None:
        path, query = self._split_path()
        if path in spot_routes.GET_ROUTES:
            self._respond(200, spot_routes.GET_ROUTES[path])
            return
        result = handle_futures("GET", path, query, self.order_book)
        self._respond_or_404(path, result)

    def do_POST(self) -> None:
        path, _ = self._split_path()
        body = self._read_form_body()
        result = handle_futures("POST", path, body, self.order_book)
        self._respond_or_404(path, result)

    def do_PUT(self) -> None:
        path, _ = self._split_path()
        body = self._read_form_body()
        result = handle_futures("PUT", path, body, self.order_book)
        self._respond_or_404(path, result)

    def do_DELETE(self) -> None:
        path, _ = self._split_path()
        body = self._read_form_body()
        result = handle_futures("DELETE", path, body, self.order_book)
        self._respond_or_404(path, result)

    def _split_path(self) -> tuple[str, dict[str, str]]:
        path, _, query_string = self.path.partition("?")
        return path, dict(parse_qsl(query_string))

    def _read_form_body(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        return dict(parse_qsl(raw.decode()))

    def _respond_or_404(self, path: str, result: tuple[int, object] | None) -> None:
        if result is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(f"binance_fake_server: no route for {path!r}".encode())
            return
        status, body = result
        self._respond(status, body)

    def _respond(self, status: int, body: object) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@dataclass(frozen=True)
class FakeServerUrls:
    """Base URLs for the two `python-binance` API families this fixture
    serves — both already in the shape `Client.API_URL`/`Client.
    FUTURES_TESTNET_URL` expect (no `{}` placeholders, so `str.format()`
    downstream is a no-op)."""

    spot: str
    futures: str


@contextmanager
def run_binance_fake_server() -> Iterator[FakeServerUrls]:
    """Starts the server on an OS-assigned free port, yields its spot and
    futures base URLs, stops it on exit. A fresh `OrderBookState` per call
    — order-lifecycle state never survives past one `with` block."""
    _Handler.order_book = OrderBookState()
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[0], server.server_address[1]
        yield FakeServerUrls(
            spot=f"http://{host}:{port}/api",
            futures=f"http://{host}:{port}/fapi",
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        # `http.server`/`socketserver` leave a small reference cycle behind
        # (the handler instance <-> the server/socket) that only becomes
        # visible as "N uncollectable objects" at Python interpreter
        # shutdown — confirmed by isolating this exact context manager and
        # observing it with gc.DEBUG_SAVEALL. Collecting immediately, while
        # this fixture's own scope still owns the cleanup, keeps that noise
        # out of whatever runs after this — a session-scoped pytest fixture
        # in particular, where "at shutdown" would otherwise land far from
        # here and look like a leak in something else entirely.
        gc.collect()
