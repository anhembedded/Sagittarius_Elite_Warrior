"""`EPIC-028O` — the reads the desks size orders with, over a real HTTP round
trip to the fake exchange server: the Futures setting and brackets
(`FuturesAccountControl`), the mark price and both venues' best bid and ask.

@details The server ignores signatures (`tests/sanity/binance_fake_server.py`).
What this proves is the path and version `python-binance` 1.0.37 sends each
request to, and the payload mapping, end to end. A route the fake does not
serve answers 404, so a wrong path fails here.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_control import (
    FuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_book_ticker_reader import (
    FuturesBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_mark_price_reader import (
    FuturesMarkPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_book_ticker_reader import (
    SpotBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_rejected_error import (
    AccountControlRejectedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server
from fake_exchange.server import FakeServerUrls


class _Credentials(IExchangeCredentialsProvider):
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used by this test")

    def remove_stored(self) -> None:
        raise AssertionError("not used by this test")


@contextmanager
def _fake_exchange() -> Iterator[FakeServerUrls]:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        yield urls


def _control() -> FuturesAccountControl:
    return FuturesAccountControl(FuturesSessionFactory(), _Credentials())


def test_a_symbol_never_changed_reads_binances_defaults() -> None:
    with _fake_exchange():
        setting = _control().symbol_setting("BTCUSDT")

    assert setting == FuturesSymbolSetting(
        "BTCUSDT", 20, MarginType.CROSSED, Decimal(2_000_000)
    )


def test_the_setting_read_back_is_the_one_just_changed() -> None:
    with _fake_exchange():
        control = _control()
        control.change_leverage("BTCUSDT", 10)
        control.change_margin_type("BTCUSDT", MarginType.ISOLATED)
        setting = control.symbol_setting("BTCUSDT")
        other = control.symbol_setting("ETHUSDT")

    assert setting == FuturesSymbolSetting(
        "BTCUSDT", 10, MarginType.ISOLATED, Decimal(10_000_000)
    )
    assert (other.leverage, other.margin_type) == (20, MarginType.CROSSED)


def test_the_brackets_arrive_in_order_with_their_maintenance_figures() -> None:
    with _fake_exchange():
        brackets = _control().leverage_brackets("BTCUSDT")

    first, second = brackets.brackets[:2]
    assert brackets.max_leverage == 125
    assert (first.notional_floor, first.notional_cap) == (0, 50_000)
    assert (first.maintenance_margin_rate, first.maintenance_amount) == (
        Decimal("0.004"),
        0,
    )
    assert (second.maintenance_margin_rate, second.maintenance_amount) == (
        Decimal("0.005"),
        50,
    )
    assert brackets.bracket_for(Decimal(2_000_000)).initial_leverage == 10


@pytest.mark.parametrize(
    "read",
    [
        lambda control: control.symbol_setting("NOPEUSDT"),
        lambda control: control.leverage_brackets("NOPEUSDT"),
    ],
    ids=["setting", "brackets"],
)
def test_an_unlisted_symbols_settings_carry_the_exchanges_code(read: object) -> None:
    with _fake_exchange(), pytest.raises(AccountControlRejectedError) as raised:
        read(_control())  # type: ignore[operator]

    assert raised.value.code == -1121


def test_a_book_read_is_one_request_and_never_a_ping() -> None:
    """PR #303 review, finding 1: the Spot public client pinged
    `GET /api/v3/ping` on every construction, so every price-button click
    was two round trips and failed on a ping failure."""
    with _fake_exchange() as urls:
        SpotBookTickerReader(SpotSessionFactory()).best_bid_ask("BTCUSDT")
        FuturesBookTickerReader(FuturesSessionFactory()).best_bid_ask("BTCUSDT")
        FuturesMarkPriceReader(FuturesSessionFactory()).mark_price("BTCUSDT")

    assert urls.requests == [
        ("GET", "/api/v3/ticker/bookTicker"),
        ("GET", "/fapi/v1/ticker/bookTicker"),
        ("GET", "/fapi/v1/premiumIndex"),
    ]


def test_the_futures_mark_price_is_read_for_a_flat_symbol() -> None:
    with _fake_exchange():
        mark = FuturesMarkPriceReader(FuturesSessionFactory()).mark_price("BTCUSDT")

    assert (mark.symbol, mark.mark_price) == ("BTCUSDT", Decimal("64000.0"))
    assert mark.as_of.year == 2023


def test_each_venue_reads_its_own_book() -> None:
    with _fake_exchange():
        futures = FuturesBookTickerReader(FuturesSessionFactory()).best_bid_ask(
            "BTCUSDT"
        )
        spot = SpotBookTickerReader(SpotSessionFactory()).best_bid_ask("BTCUSDT")

    assert futures == BestBidAsk(
        "BTCUSDT",
        Decimal("63999.9"),
        Decimal("2.500"),
        Decimal("64000.1"),
        Decimal("1.750"),
    )
    assert (spot.bid_price, spot.ask_price) == (
        Decimal("49999.99"),
        Decimal("50000.01"),
    )


@pytest.mark.parametrize(
    "read",
    [
        lambda: FuturesMarkPriceReader(FuturesSessionFactory()).mark_price("NOPEUSDT"),
        lambda: FuturesBookTickerReader(FuturesSessionFactory()).best_bid_ask(
            "NOPEUSDT"
        ),
        lambda: SpotBookTickerReader(SpotSessionFactory()).best_bid_ask("NOPEUSDT"),
    ],
    ids=["futures-mark", "futures-book", "spot-book"],
)
def test_an_unlisted_symbol_is_the_ports_error_with_the_cause_chained(
    read: object,
) -> None:
    with _fake_exchange(), pytest.raises(MarketPriceUnavailableError) as raised:
        read()  # type: ignore[operator]

    assert "Invalid symbol" in str(raised.value.__cause__)
