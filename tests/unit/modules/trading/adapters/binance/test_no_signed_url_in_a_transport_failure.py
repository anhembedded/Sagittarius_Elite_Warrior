"""`BUG-180` / `EPIC-035O` — a transport failure carries no signed request URL.

`requests` words a connection error with the request's whole URL, and a signed
Binance request holds the `signature` in it. The text is in the
exception, in its chained cause and in every traceback printed from either, so a
log line written anywhere above the transport (`logger.exception` on the cancel
path, `classify_connection_failure`, a screen) carried it.

The real python-binance `Client` is built by the one constructor (`new_client`)
over a fake transport at `requests.Session`'s verbs: the pings and the clock
answer, and the signed request raises what `requests` raises when the network is
down. Nothing here is a real key, signature or exchange.
"""

from __future__ import annotations

import logging
import re
import traceback
from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

import pytest
import requests
from requests.adapters import HTTPAdapter
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    BotIdentity,
    BotOrderGateway,
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.binance_client_builder import (
    new_client,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    classify_connection_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_failure import (
    FailureKind,
    classify_exchange_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.transport_failure_redaction import (
    redact_transport_failure,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from urllib3.exceptions import MaxRetryError, NewConnectionError

#: Made-up values shaped like a signed query; none was ever a credential.
_SIGNATURE = "0123456789abcdef0123456789abcdef"
_TIMESTAMP = "1791380000000"
_SIGNED_QUERY = f"timestamp={_TIMESTAMP}&signature={_SIGNATURE}"
_FORBIDDEN = (_SIGNATURE,)
_HOST = "api.binance.com"
_CLIENT_ORDER_ID = "SEW-abc123-0123456789"


class _Answer(requests.Response):
    def __init__(self, body: bytes) -> None:
        super().__init__()
        self.status_code = 200
        self._content = body


class _FakeTransport:
    """The network under `requests`' adapter: the construction-time ping and
    the clock answer; a signed request fails as `requests` fails with the
    network down."""

    def __init__(self) -> None:
        self.signed_requests = 0

    def send(self, request: requests.PreparedRequest) -> _Answer:
        url = request.url or ""
        if url.endswith("/ping"):
            return _Answer(b"{}")
        if url.endswith("/time"):
            return _Answer(b'{"serverTime": 1791380000000}')
        self.signed_requests += 1
        raise _connection_error(request)


def _connection_error(
    request: requests.PreparedRequest,
) -> requests.exceptions.ConnectionError:
    """What `HTTPAdapter.send` raises over urllib3 2.x: `ConnectionError(e,
    request=request)` for a `MaxRetryError` `e` that words the URL, query
    included."""
    path = (request.url or "").split(_HOST, 1)[1]
    url = f"{path.split('?')[0]}?{_SIGNED_QUERY}"
    refused = NewConnectionError(None, "Failed to establish a new connection")  # type: ignore[arg-type]
    try:
        raise MaxRetryError(None, url, refused)  # type: ignore[arg-type]
    except MaxRetryError as exhausted:
        try:
            raise requests.exceptions.ConnectionError(exhausted, request=request)
        except requests.exceptions.ConnectionError as wrapped:
            return wrapped


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> _FakeTransport:
    fake = _FakeTransport()
    monkeypatch.setattr(
        HTTPAdapter,
        "send",
        lambda _adapter, request, **_options: fake.send(request),
    )
    return fake


def _signed_client() -> Any:
    return new_client(
        TradingVenue.SPOT_MAINNET, ExchangeCredentials("api-key", "api-secret")
    )


def _everything_written_about(exc: BaseException) -> str:
    """The exception's text in each form a log can print it, chain included."""
    chain: list[str] = []
    link: BaseException | None = exc
    while link is not None:
        chain += [str(link), repr(link)]
        link = link.__cause__ or link.__context__
    return "\n".join([*chain, "".join(traceback.format_exception(exc))])


def _failure_of(call: Callable[[], object]) -> BaseException:
    with pytest.raises(requests.exceptions.RequestException) as caught:
        call()
    return caught.value


def test_a_cancel_failure_logs_no_signature(
    transport: _FakeTransport, caplog: pytest.LogCaptureFixture
) -> None:
    """Red before: the gateway's `logger.exception` printed the traceback of
    the chained `requests` error, whose text held `?timestamp=…&signature=…`.
    The path is the bot's own: gateway → trading's cancel → python-binance."""
    client = _signed_client()
    ports = Mock()
    ports.order_submission.cancel.side_effect = lambda symbol, client_order_id: (
        client.cancel_order(symbol=symbol, origClientOrderId=client_order_id)
    )
    gateway = BotOrderGateway(
        ports, BotIdentity("bot:abc123", "abc123", "BTCUSDT"), Mock()
    )

    with caplog.at_level(logging.DEBUG):
        outcome = gateway.cancel(_CLIENT_ORDER_ID)

    assert transport.signed_requests == 1, "the cancel reached the transport"
    assert outcome.kind is OrderOutcomeKind.FAULT
    written = caplog.text + outcome.detail
    assert "cancel" in written, "the failure itself is still in the log"
    assert _HOST in written or "ConnectionError" in written
    for secret in _FORBIDDEN:
        assert secret not in written, f"{secret!r} reached the log"


@pytest.mark.parametrize(
    "call",
    [
        lambda client: client.cancel_order(symbol="BTCUSDT", origClientOrderId="x"),
        lambda client: client.cancel_all_open_orders(symbol="BTCUSDT"),
        lambda client: client.create_order(
            symbol="BTCUSDT", side="BUY", type="MARKET", quantity="1"
        ),
        lambda client: client.get_open_orders(symbol="BTCUSDT"),
        lambda client: client.get_account(),
    ],
    ids=["cancel", "cancel-all", "order-send", "open-orders", "account"],
)
def test_every_signed_call_of_the_client_fails_without_the_query(
    transport: _FakeTransport, call: Callable[[Any], object]
) -> None:
    """The mechanism, not the cancel call site: the sanitiser sits on the
    client every path is built from, so a new caller inherits it."""
    client = _signed_client()

    failure = _failure_of(lambda: call(client))

    written = _everything_written_about(failure)
    for secret in _FORBIDDEN:
        assert secret not in written, f"{secret!r} in the exception"


def test_the_failure_is_still_a_transport_failure_after_the_query_is_removed(
    transport: _FakeTransport,
) -> None:
    """The retry policy and every `except RequestException` read the type."""
    failure = _failure_of(lambda: _signed_client().get_account())

    assert isinstance(failure, requests.exceptions.ConnectionError)
    assert classify_exchange_failure(failure, 0).kind is FailureKind.TRANSIENT
    assert "/api/v3/account" in str(failure), "the path stays: the failure is named"


def test_a_connection_check_logs_no_signature(
    transport: _FakeTransport, caplog: pytest.LogCaptureFixture
) -> None:
    """The first form of the bug: `classify_connection_failure` logged
    `str(exc)` at ERROR for any failure it has no name for."""
    failure = _failure_of(lambda: _signed_client().get_account())

    with caplog.at_level(logging.DEBUG):
        classify_connection_failure(failure, "Spot Mainnet")

    assert "Spot Mainnet connection check failed" in caplog.text
    for secret in _FORBIDDEN:
        assert secret not in caplog.text


def test_a_failure_without_a_query_is_left_as_it_was(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plain = requests.exceptions.ConnectionError("Connection aborted.")

    def send(_adapter: HTTPAdapter, request: requests.PreparedRequest, **_o: Any):
        if (request.url or "").endswith(("/ping", "/time")):
            return _Answer(b'{"serverTime": 1791380000000}')
        raise plain

    monkeypatch.setattr(HTTPAdapter, "send", send)

    failure = _failure_of(lambda: _signed_client().get_account())

    assert str(failure) == "Connection aborted."


def test_a_listen_key_and_an_api_key_in_a_failure_are_removed_with_the_signature() -> (
    None
):
    """One redactor for the request material (`user_stream_supervisor` words its
    failures through the same function): the listen key of a user-data request
    and a header-signed key go with the signature, anywhere in the chain."""
    cause = OSError("GET /api/v3/userDataStream?listenKey=LISTENKEYVALUE failed")
    failure = requests.exceptions.ConnectionError(
        "X-MBX-APIKEY: APIKEYVALUE refused", cause
    )
    failure.__cause__ = cause

    redact_transport_failure(failure)

    written = _everything_written_about(failure)
    assert "LISTENKEYVALUE" not in written
    assert "APIKEYVALUE" not in written
    assert "/api/v3/userDataStream" in written, "the path stays"


def test_the_request_a_failure_carries_holds_no_signature_or_key(
    transport: _FakeTransport,
) -> None:
    """Review of PR 447, finding 2: `RequestException.request` is the prepared
    request, whose URL holds the signature and whose header holds the API key.
    Nothing logs the attribute today; a caller that printed it would."""
    failure = _failure_of(
        lambda: _signed_client().cancel_order(symbol="BTCUSDT", origClientOrderId="x")
    )

    request = failure.request  # type: ignore[attr-defined]
    assert request is not None, "the request stays: only its secrets go"
    body = request.body.decode() if isinstance(request.body, bytes) else request.body
    assert "signature=" in (request.url + (body or "")), "the signed form is checked"
    for text in (request.url, body or ""):
        assert re.search(r"signature=(?!<redacted>)", text) is None
    assert request.headers["X-MBX-APIKEY"] == "<redacted>"
