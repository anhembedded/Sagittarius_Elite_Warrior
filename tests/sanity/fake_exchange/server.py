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
from .history_log import now_ms
from .order_book_state import OrderBookState
from .rate_limit_policy import RateLimitPolicy
from .request_weight import WeightMeter
from .sapi_routes import ApiRestrictions
from .sapi_routes import handle as handle_sapi
from .spot_account_state import SpotAccountState
from .spot_routes import handle as handle_spot

#: What a proxy or the exchange itself serves while it is under maintenance:
#: a web page, not an API reply (`EPIC-034D`).
MAINTENANCE_PAGE = (
    "<html><head><title>503 Service Temporarily Unavailable</title></head>"
    "<body>The service is under maintenance.</body></html>"
)


class MaintenanceSwitch:
    """While `on`, every request is answered with `MAINTENANCE_PAGE` and a 503."""

    def __init__(self) -> None:
        self.on = False


@dataclass
class FaultAnswer:
    """One request the fake exchange answers wrongly: the first request whose
    path contains `path_part` gets `status`, `headers` and `body`. With `drop`
    it gets no answer at all: the connection is closed, as a reset does."""

    path_part: str
    status: int = 200
    body: object = ""
    headers: dict[str, str] = field(default_factory=dict)
    drop: bool = False


class FaultPlan:
    """`EPIC-035D` — the faults a test queues for the next matching requests.

    Each `FaultAnswer` is used once, in the order queued, by the first request it
    matches; a request nothing matches is served normally. The server also records
    when it was asked (`requests`), so a test can say how many requests a fault
    cost.
    """

    def __init__(self) -> None:
        self.queued: list[FaultAnswer] = []

    def take(self, path: str) -> FaultAnswer | None:
        for index, fault in enumerate(self.queued):
            if fault.path_part in path:
                return self.queued.pop(index)
        return None


class KeyPolicy:
    """Which API keys this fake environment knows (`BUG-176`).

    By default every key is known, as before. Once `known` is a set, a signed request
    (one carrying `signature`, the only kind Binance checks the key of) answers `-2008`
    for a key outside it and `-2015` for one in `refused`: known, but refused here,
    like an IP off the key's allowlist.
    """

    def __init__(self) -> None:
        self.known: set[str] | None = None
        self.refused: set[str] = set()

    def rejection(self, api_key: str | None) -> tuple[int, object] | None:
        if self.known is None:
            return None
        if api_key in self.refused:
            return 401, {
                "code": -2015,
                "msg": "Invalid API-key, IP, or permissions for action.",
            }
        if api_key not in self.known:
            return 401, {"code": -2008, "msg": "Invalid Api-Key ID."}
        return None


class ClockPolicy:
    """Binance's timestamp rule on signed requests (`BUG-221`); on by default since `EPIC-037E`.

    With `enforcing` on, a signed request whose `timestamp` is more than 1000 ms ahead of the
    exchange's clock (`history_log.now_ms`, which `exchange_clock_skewed_by` moves), or older
    than its `recvWindow` (5000 ms by default), answers `-1021` as Binance does. Binance's
    message always says "1000ms ahead", whatever the real gap.
    """

    AHEAD_LIMIT_MS = 1000
    DEFAULT_RECV_WINDOW_MS = 5000

    def __init__(self) -> None:
        self.enforcing = True
        #: Signed requests refused with `-1021`, to say what a step of the clock cost.
        self.rejected = 0

    def rejection(self, params: dict[str, str]) -> tuple[int, object] | None:
        if not self.enforcing or "signature" not in params or "timestamp" not in params:
            return None
        server_ms = now_ms()
        sent_ms = int(params["timestamp"])
        window_ms = int(params.get("recvWindow", self.DEFAULT_RECV_WINDOW_MS))
        if (
            sent_ms < server_ms + self.AHEAD_LIMIT_MS
            and server_ms - sent_ms <= window_ms
        ):
            return None
        self.rejected += 1
        return 400, {
            "code": -1021,
            "msg": "Timestamp for this request was 1000ms ahead of the server's time.",
        }


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
    maintenance: MaintenanceSwitch
    api_restrictions: ApiRestrictions
    keys: KeyPolicy
    faults: FaultPlan
    clock: ClockPolicy
    #: `BUG-216` — what each request weighs; the minute's total goes back in the
    #: `X-MBX-USED-WEIGHT-1M` header, as the exchange does.
    weights: WeightMeter
    #: `EPIC-037E` — set `.limit` to answer 429, then 418, past that weight per minute.
    rate_limit: RateLimitPolicy
    #: The fault this request was given, if any (one handler instance per request).
    _fault: FaultAnswer | None = None
    _used_weight: int = 0

    def log_message(self, format: str, *args: object) -> None:
        pass  # Silence per-request access logs — this is a test fixture,
        # not a service anyone needs to watch run.

    def do_GET(self) -> None:
        path, query = self._split_path()
        self._respond_or_404(path, self._dispatch("GET", path, query))

    def do_POST(self) -> None:
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

    def _dispatch(
        self, method: str, path: str, params: dict[str, str]
    ) -> tuple[int, object] | None:
        self.requests.append((method, path))
        self._used_weight = self.weights.charge(method, path, params)
        self._fault = self.faults.take(path)
        if self._fault is not None:
            return self._fault.status, self._fault.body
        limited = self.rate_limit.refusal(
            self._used_weight, *self.weights.minute_position()
        )
        if limited is not None:
            status, body, headers = limited
            self._fault = FaultAnswer("", status, body, headers)
            return status, body
        if self.maintenance.on:
            return 503, MAINTENANCE_PAGE
        if "signature" in params:
            stale = self.clock.rejection(params)
            if stale is not None:
                return stale
            rejection = self.keys.rejection(self.headers.get("X-MBX-APIKEY"))
            if rejection is not None:
                return rejection
        if path.startswith("/sapi/"):
            return handle_sapi(method, path, self.api_restrictions)
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
        if self._fault is not None and self._fault.drop:
            self.close_connection = True
            return  # no answer: the connection ends, as a reset does
        if result is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(f"binance_fake_server: no route for {path!r}".encode())
            return
        status, body = result
        self._respond(status, body)

    def _respond(self, status: int, body: object) -> None:
        is_page = isinstance(body, str)
        payload = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html" if is_page else "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-MBX-USED-WEIGHT-1M", str(self._used_weight))
        for name, value in (self._fault.headers if self._fault else {}).items():
            self.send_header(name, value)
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
    #: `EPIC-034E` — Spot mainnet's wallet family (`Client.MARGIN_API_URL`).
    margin: str
    #: Every `(method, path)` the server answered (`EPIC-028P`). The same list
    #: the server appends to, so it grows while the `with` block runs.
    requests: list[tuple[str, str]] = field(default_factory=list)
    #: `EPIC-028O` — the live Spot state, so a test can move a symbol's last
    #: price (`SpotAccountState.set_last_price`) and watch a stop trigger.
    spot_account: SpotAccountState = field(default_factory=SpotAccountState)
    #: `EPIC-028O` — the live Futures state, so a test can switch the account
    #: to Multi-Assets mode or read its positions.
    futures_book: OrderBookState = field(default_factory=OrderBookState)
    #: `EPIC-034D` — turn `.on` to make the whole exchange answer a maintenance page.
    maintenance: MaintenanceSwitch = field(default_factory=MaintenanceSwitch)
    #: `EPIC-034E` — what the fake exchange says the API key may do.
    api_restrictions: ApiRestrictions = field(default_factory=ApiRestrictions)
    #: `BUG-176` — which keys this environment knows; every key until a test narrows it.
    keys: KeyPolicy = field(default_factory=KeyPolicy)
    #: `EPIC-035D` — queue wrong answers (a 429 with `Retry-After`, a dropped
    #: connection) for the next requests that match.
    faults: FaultPlan = field(default_factory=FaultPlan)
    #: `BUG-216` — the weight of every request answered, per path and per minute.
    weights: WeightMeter = field(default_factory=WeightMeter)
    #: `BUG-221` — set `.enforcing` to make a stale timestamp answer `-1021`, as Binance does.
    clock: ClockPolicy = field(default_factory=ClockPolicy)
    #: `EPIC-037E` — set `.limit` to make the exchange refuse with 429, then 418.
    rate_limit: RateLimitPolicy = field(default_factory=RateLimitPolicy)


@contextmanager
def run_binance_fake_server() -> Iterator[FakeServerUrls]:
    """Starts the server on an OS-assigned free port, yields its spot and
    futures base URLs, stops it on exit. A fresh `OrderBookState` and
    `SpotAccountState` per call — order-lifecycle state never survives past
    one `with` block. Each call has a handler class of its own, so several servers
    can run at once (`BUG-176`: mainnet and both testnets, each knowing other keys)."""
    handler = type("_ServerHandler", (_Handler,), {})
    handler.order_book = OrderBookState()
    handler.spot_account = SpotAccountState()
    handler.requests = []
    handler.maintenance = MaintenanceSwitch()
    handler.api_restrictions = ApiRestrictions()
    handler.keys = KeyPolicy()
    handler.faults = FaultPlan()
    handler.weights = WeightMeter()
    handler.clock = ClockPolicy()
    handler.rate_limit = RateLimitPolicy()
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[0], server.server_address[1]
        yield FakeServerUrls(
            spot=f"http://{host}:{port}/api",
            futures=f"http://{host}:{port}/fapi",
            margin=f"http://{host}:{port}/sapi",
            requests=handler.requests,
            spot_account=handler.spot_account,
            futures_book=handler.order_book,
            maintenance=handler.maintenance,
            api_restrictions=handler.api_restrictions,
            keys=handler.keys,
            faults=handler.faults,
            weights=handler.weights,
            clock=handler.clock,
            rate_limit=handler.rate_limit,
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
