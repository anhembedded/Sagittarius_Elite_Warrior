"""`EPIC-034D` — one account read is one snapshot, or one named failure.

The ports are the repository's verified fakes where one exists and small
subclasses of the real ABC where not; each read can be made to fail on its
own, so a test proves which one stopped the snapshot.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.account.composed_venue_account_reader import (
    ComposedVenueAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    SpotAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate_unavailable_error import (
    CommissionRateUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_book_ticker_reader import (
    IBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_commission_rate_reader import (
    ICommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_market_metadata_provider import (
    FakeMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
_SYMBOL = "BTCUSDT"
_DUST = Decimal("0.00000001")


class _Commission(ICommissionRateReader):
    def __init__(self, error: CommissionRateUnavailableError | None = None) -> None:
        self._error = error

    def commission_rate(self, symbol: str) -> CommissionRate:
        if self._error is not None:
            raise self._error
        return CommissionRate(symbol, maker=Decimal("0.001"), taker=Decimal("0.001"))


class _Book(IBookTickerReader):
    def __init__(
        self,
        book: BestBidAsk | None = None,
        error: MarketPriceUnavailableError | None = None,
    ) -> None:
        self._book = book or BestBidAsk(
            _SYMBOL, Decimal(99), Decimal(1), Decimal(101), Decimal(1)
        )
        self._error = error

    def best_bid_ask(self, symbol: str) -> BestBidAsk:
        if self._error is not None:
            raise self._error
        return self._book


def _rules() -> SymbolOrderMetadata:
    return SymbolOrderMetadata(
        symbol=_SYMBOL,
        status="TRADING",
        step_size=Decimal("0.00001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(5),
        quantity_precision=None,
        price_precision=None,
        fetched_at=_NOW,
    )


def _status(**changes: object) -> ExchangeConnectionStatus:
    status = ExchangeConnectionStatus(
        venue=TradingVenue.SPOT_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=0,
        usdt_balance=Decimal(1000),
        position_mode=None,
        margin_type=None,
        open_position_count=None,
        holdings=(
            SpotHolding("USDT", Decimal(900), Decimal(100), _DUST),
            SpotHolding("BTC", Decimal("0.5"), Decimal(0), _DUST),
            SpotHolding("DOGE", Decimal("0.000000001"), Decimal(0), _DUST),
        ),
        equity=Decimal(1050),
        summary=SpotAccountSummary(
            venue=TradingVenue.SPOT_TESTNET,
            available_balance=Decimal(900),
            equity=Decimal(1050),
            quote_asset="USDT",
            quote_free=Decimal(900),
            quote_locked=Decimal(100),
        ),
        can_trade=True,
    )
    return replace(status, **changes)  # type: ignore[arg-type]


def _reader(
    status: ExchangeConnectionStatus | None = None,
    commission: ICommissionRateReader | None = None,
    book: IBookTickerReader | None = None,
    rules: tuple[SymbolOrderMetadata, ...] = (),
) -> ComposedVenueAccountReader:
    context = replace(
        fake_venue_context(
            TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(status or _status()),
            metadata_provider=FakeMarketMetadataProvider(rules or (_rules(),)),
        ),
        commission_reader=commission or _Commission(),
        book_ticker_reader=book or _Book(),
    )
    return ComposedVenueAccountReader(
        AccountSource.SPOT_TESTNET, context, clock=lambda: _NOW
    )


def test_one_read_is_one_snapshot_of_everything_a_design_needs() -> None:
    snapshot = _reader().read(_SYMBOL)

    assert isinstance(snapshot, VenueAccountSnapshot)
    assert snapshot.source is AccountSource.SPOT_TESTNET
    assert snapshot.read_at == _NOW
    assert snapshot.available == Decimal(900)  # free, not the 1000 wallet
    assert snapshot.can_trade is True
    assert snapshot.commission.taker == Decimal("0.001")
    assert snapshot.rules.tick_size == Decimal("0.01")
    assert snapshot.price == Decimal(101)  # the ask: a buy pays it
    assert snapshot.free_of("BTC") == Decimal("0.5")
    assert snapshot.free_of("ETH") == Decimal(0)
    assert "DOGE" not in {holding.asset for holding in snapshot.holdings}


def test_an_empty_ask_side_prices_at_the_bid() -> None:
    book = BestBidAsk(_SYMBOL, Decimal(99), Decimal(1), Decimal(0), Decimal(0))

    snapshot = _reader(book=_Book(book)).read(_SYMBOL)

    assert isinstance(snapshot, VenueAccountSnapshot)
    assert snapshot.price == Decimal(99)


def test_a_key_the_exchange_rejects_is_named_and_reads_nothing_else() -> None:
    rejected = _status(
        reachable=False,
        failure=ConnectionFailureKind.KEY_REJECTED,
        summary=None,
        usdt_balance=None,
    )

    answer = _reader(rejected, commission=_Commission(_boom_commission())).read(_SYMBOL)

    assert answer == ConnectFailure(
        AccountSource.SPOT_TESTNET, ConnectionFailureKind.KEY_REJECTED, "the account"
    )


def test_a_maintenance_page_is_named_maintenance() -> None:
    down = _status(
        reachable=False, failure=ConnectionFailureKind.MAINTENANCE, summary=None
    )

    answer = _reader(down).read(_SYMBOL)

    assert isinstance(answer, ConnectFailure)
    assert answer.kind is ConnectionFailureKind.MAINTENANCE


def test_a_reachable_account_with_a_failure_is_still_a_failure() -> None:
    hedge = _status(failure=ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED)

    answer = _reader(hedge).read(_SYMBOL)

    assert isinstance(answer, ConnectFailure)
    assert answer.kind is ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED


@pytest.mark.parametrize(
    ("reader", "what"),
    [
        (lambda: _reader(commission=_Commission(_boom_commission())), "the commission"),
        (
            lambda: _reader(book=_Book(error=MarketPriceUnavailableError("down"))),
            "the price",
        ),
        (lambda: _reader(rules=(replace(_rules(), symbol="ETHUSDT"),)), "the filters"),
    ],
)
def test_each_read_that_fails_names_itself(reader, what: str) -> None:  # type: ignore[no-untyped-def]
    answer = reader().read(_SYMBOL)

    assert isinstance(answer, ConnectFailure)
    assert answer.detail.startswith(what)


def test_a_book_with_no_orders_is_no_price() -> None:
    empty = BestBidAsk(_SYMBOL, Decimal(0), Decimal(0), Decimal(0), Decimal(0))

    answer = _reader(book=_Book(empty)).read(_SYMBOL)

    assert isinstance(answer, ConnectFailure)
    assert answer.detail.startswith("the price")


def test_an_account_without_a_balance_is_not_a_snapshot() -> None:
    answer = _reader(_status(summary=None, usdt_balance=None)).read(_SYMBOL)

    assert isinstance(answer, ConnectFailure)
    assert answer.detail == "the balance"


def test_a_flag_the_exchange_did_not_send_stays_unknown() -> None:
    snapshot = _reader(_status(can_trade=None)).read(_SYMBOL)

    assert isinstance(snapshot, VenueAccountSnapshot)
    assert snapshot.can_trade is None


def _boom_commission() -> CommissionRateUnavailableError:
    return CommissionRateUnavailableError("down")
