"""
`EPIC-009` D6 — a local server speaking Binance's REST protocol.

Exists so the real `python-binance` client can run completely unchanged and
still never touch the network. This is a deliberate rejection of the cheaper
option: a hand-written substitute for `IExchangeClient` would bypass
`PythonBinanceClient` entirely — its kline mapping, its generator-based
pagination, its cancellation checks, all of `python-binance`'s own HTTP
behavior — and that is exactly the shape that produced `BUG-026` and
`BUG-027`: hand-written port implementations that silently fell behind the
real interface. Here, only the base URL moves; every line of the real
adapter stack still runs.

Only the three REST operations this application actually calls are served —
verified against `src/infrastructure/binance/client.py`, not assumed:

    GET /api/v3/ping           Client()'s own constructor calls this
                                 (`ping=True` by default) — this alone was
                                 `BUG-045`'s trigger: resolving a handler
                                 through the DI container constructs a
                                 `PythonBinanceClient`, which reaches the
                                 network merely by being resolved.
    GET /api/v3/exchangeInfo   PythonBinanceClient.get_available_symbols()
    GET /api/v3/klines         PythonBinanceClient's kline fetch paths
                                 (paginated by get_historical_klines_generator)

Any other path returns 404 rather than a plausible-looking empty success —
an unexpected call should be loud, not silently swallowed.

Responses are fixed and deterministic. A fake that generates time-dependent
or random data would reintroduce the flakiness this tier exists to avoid.
"""

from __future__ import annotations

import gc
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

#: A tiny, fixed exchange-info payload — enough shape for
#: `get_available_symbols()` to parse successfully, not a realistic catalog.
_EXCHANGE_INFO = {
    "timezone": "UTC",
    "serverTime": 0,
    "symbols": [
        {"symbol": "BTCUSDT", "status": "TRADING"},
        {"symbol": "ETHUSDT", "status": "TRADING"},
    ],
}

_ROUTES: dict[str, object] = {
    "/api/v3/ping": {},
    "/api/v3/exchangeInfo": _EXCHANGE_INFO,
    # Empty on purpose: this tier proves resolution and wiring, not kline
    # data — an empty page terminates get_historical_klines_generator's
    # pagination immediately instead of looping.
    "/api/v3/klines": [],
}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # Silence per-request access logs — this is a test fixture, not
        # a service anyone needs to watch run.

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's own name
        path = self.path.split("?", 1)[0]
        body = _ROUTES.get(path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(f"binance_fake_server: no route for {path!r}".encode())
            return

        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@contextmanager
def run_binance_fake_server() -> Iterator[str]:
    """Starts the server on an OS-assigned free port, yields its base URL
    (already in the `.../api` shape `python-binance`'s `Client.API_URL`
    expects — no `{}` placeholders, so `str.format()` on it downstream is a
    no-op), stops it on exit.
    """
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[0], server.server_address[1]
        yield f"http://{host}:{port}/api"
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
