"""`EPIC-021J`/`EPIC-027J` — HTTP plumbing for the Binance-protocol fake
server: parses each request, dispatches to `spot_routes`/`futures_routes`
by path prefix, and owns the two pieces of state — `OrderBookState`
(Futures) and `SpotAccountState` (Spot), independent facts, never a union
— for the lifetime of one `run_binance_fake_server()` call.

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
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl

from .futures_routes import handle as handle_futures
from .order_book_state import OrderBookState
from .spot_account_state import SpotAccountState
from .spot_routes import handle as handle_spot


class _Handler(BaseHTTPRequestHandler):
    #: Set per-server-instance by `run_binance_fake_server()` via
    #: `HTTPServer`'s own `RequestHandlerClass` attribute-sharing —
    #: `BaseHTTPRequestHandler` is instantiated fresh per request, so state
    #: cannot live on `self`; it lives on the class, scoped by the
    #: contextmanager's own `try`/`finally` instead.
    order_book: OrderBookState
    spot_account: SpotAccountState
    #: `EPIC-028P` — every `(method, path)` this server answered, in order,
    #: so a test can prove a command addressed to one venue sent nothing to
    #: the other's API family.
    requests: list[tuple[str, str]]
    #: `BOT-169` — while set, every request is answered with a gateway's HTML
    #: `502` page, as the Spot Testnet did on 2026-10-07.
    outage: threading.Event

    def log_message(self, format: str, *args: object) -> None:
        pass  # Silence per-request access logs — this is a test fixture,
        # not a service anyone needs to watch run.

    def do_GET(self) -> None:
        if self._answer_outage():
            return
        path, query = self._split_path()
        self._respond_or_404(path, self._dispatch("GET", path, query))

    def do_POST(self) -> None:
        if self._answer_outage():
            return
        path, _ = self._split_path()
        body = self._read_form_body()
        self._respond_or_404(path, self._dispatch("POST", path, body))

    def do_PUT(self) -> None:
        path, _ = self._split_path()
        body = self._read_form_body()
        self._respond_or_404(path, self._dispatch("PUT", path, body))

    def do_DELETE(self) -> None:
        path, _ = self._split_path()
        body = self._read_form_body()
        self._respond_or_404(path, self._dispatch("DELETE", path, body))

    def _answer_outage(self) -> bool:
        if not self.outage.is_set():
            return False
        page = b"<html>\r\n<head><title>502 Bad Gateway</title></head>\r\n<body>\r\n<center><h1>502 Bad Gateway</h1></center>\r\n<hr><center>nginx</center>\r\n</body>\r\n</html>\r\n"
        self.send_response(502)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)
        return True

    def _dispatch(
        self, method: str, path: str, params: dict[str, str]
    ) -> tuple[int, object] | None:
        self.requests.append((method, path))
        if path.startswith("/api/"):
            return handle_spot(method, path, params, self.spot_account)
        return handle_futures(method, path, params, self.order_book)

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
    #: Every `(method, path)` the server answered (`EPIC-028P`). The same list
    #: the server appends to, so it grows while the `with` block runs.
    requests: list[tuple[str, str]] = field(default_factory=list)
    #: `EPIC-028O` — the live Spot state, so a test can move a symbol's last
    #: price (`SpotAccountState.set_last_price`) and watch a stop trigger.
    spot_account: SpotAccountState = field(default_factory=SpotAccountState)
    #: `EPIC-028O` — the live Futures state, so a test can switch the account
    #: to Multi-Assets mode or read its positions.
    futures_book: OrderBookState = field(default_factory=OrderBookState)
    #: `BOT-169` — set it and every request answers an HTML `502` page.
    outage: threading.Event = field(default_factory=threading.Event)


@contextmanager
def run_binance_fake_server() -> Iterator[FakeServerUrls]:
    """Starts the server on an OS-assigned free port, yields its spot and
    futures base URLs, stops it on exit. A fresh `OrderBookState` and
    `SpotAccountState` per call — order-lifecycle state never survives past
    one `with` block."""
    _Handler.order_book = OrderBookState()
    _Handler.spot_account = SpotAccountState()
    _Handler.requests = []
    _Handler.outage = threading.Event()
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[0], server.server_address[1]
        yield FakeServerUrls(
            spot=f"http://{host}:{port}/api",
            futures=f"http://{host}:{port}/fapi",
            requests=_Handler.requests,
            spot_account=_Handler.spot_account,
            futures_book=_Handler.order_book,
            outage=_Handler.outage,
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
