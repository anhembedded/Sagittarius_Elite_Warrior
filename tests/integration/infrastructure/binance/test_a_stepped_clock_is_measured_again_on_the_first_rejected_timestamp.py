"""`BUG-221` — a machine clock that steps after a session was opened does not cost a request.

@details The session measures the exchange's clock once, when it is opened, and the venue
re-opens it only when that reading is ten minutes old. A clock that steps inside those ten
minutes made every signed request answer `-1021` (a position read every 2.5 s, the close
of a halted bot included) until the reading expired. The real python-binance `Client`, the
real `FuturesSessionFactory`, `VenueSessions` and `ResilientSession` talk to the loopback
fake exchange, which applies Binance's timestamp rule (`ClockPolicy`).
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    named_failure_kind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionClient,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "sanity"))
from binance_fake_server import FakeServerUrls, run_binance_fake_server
from fake_exchange.history_log import exchange_clock_skewed_by
from fake_exchange.server import FaultAnswer

_KEYS = ExchangeCredentials(api_key="k", api_secret="s")
#: The machine's clock steps 3 s ahead of the exchange's, after the session measured it.
_STEP_MS = -3000
_TIME = "/fapi/v1/time"
_POSITIONS = "/fapi/v3/positionRisk"
_LEVERAGE = "/fapi/v1/leverage"
_SPOT_TIME = "/api/v3/time"
_SPOT_OPEN_ORDERS = "/api/v3/openOrders"
_TOLERANCE_MS = 500


def _count(urls: FakeServerUrls, path: str) -> int:
    return sum(1 for _, seen in urls.requests if seen == path)


def _opened(urls: FakeServerUrls) -> ITradingSessionClient:
    """A signed session measured while the clocks agree, with the exchange enforcing."""
    session = FuturesSessionFactory().create_trading_client(_KEYS)
    urls.clock.enforcing = True
    return session


@pytest.fixture
def urls() -> Iterator[FakeServerUrls]:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        yield urls


def test_a_read_after_a_clock_step_is_sent_again_once_the_clock_is_measured(
    urls: FakeServerUrls,
) -> None:
    session = _opened(urls)

    with exchange_clock_skewed_by(_STEP_MS):
        session.futures_position_information()

        assert urls.clock.rejected == 1
        assert _count(urls, _POSITIONS) == 2, "refused once, then sent again"
        assert _count(urls, _TIME) == 2, "the open's reading and one more"
        assert abs(session.timestamp_offset - _STEP_MS) < _TOLERANCE_MS

        session.futures_position_information()

        assert urls.clock.rejected == 1, "the repaired offset serves the next request"
        assert _count(urls, _TIME) == 2


def test_an_order_side_request_after_a_clock_step_is_repaired_too(
    urls: FakeServerUrls,
) -> None:
    """A leverage change is sent at most once on a transport failure; a rejected timestamp
    is not a transport failure, the exchange refused it before reading it."""
    session = _opened(urls)

    with exchange_clock_skewed_by(_STEP_MS):
        session.futures_change_leverage(symbol="ETHUSDT", leverage=3)

    assert urls.clock.rejected == 1
    assert _count(urls, _LEVERAGE) == 2


def test_a_skew_the_measurement_cannot_cure_is_reported_as_clock_skew_and_not_looped(
    urls: FakeServerUrls,
) -> None:
    session = _opened(urls)
    refusal = {"code": -1021, "msg": "Timestamp for this request was 1000ms ahead."}
    urls.faults.queued = [
        FaultAnswer(_POSITIONS, status=400, body=refusal),
        FaultAnswer(_POSITIONS, status=400, body=refusal),
    ]

    with pytest.raises(BinanceAPIException) as raised:
        session.futures_position_information()

    assert named_failure_kind(raised.value) is ConnectionFailureKind.CLOCK_SKEW
    assert _count(urls, _POSITIONS) == 2, (
        "sent, measured, sent once more, then given up"
    )
    assert _count(urls, _TIME) == 2
    assert session.futures_position_information() is not None


def test_a_spot_read_after_a_clock_step_is_sent_again_once_the_clock_is_measured(
    urls: FakeServerUrls,
) -> None:
    """Spot measures with `get_server_time`, Futures with `futures_time`: a swapped flag in the
    resync would pass the Futures tests, because the fake serves both from one clock."""
    session = SpotSessionFactory().create_trading_client(_KEYS)
    urls.clock.enforcing = True

    with exchange_clock_skewed_by(_STEP_MS):
        session.get_open_orders(symbol="BTCUSDT")

    assert urls.clock.rejected == 1
    assert _count(urls, _SPOT_OPEN_ORDERS) == 2
    assert _count(urls, _SPOT_TIME) == 2
    assert abs(session.timestamp_offset - _STEP_MS) < _TOLERANCE_MS
