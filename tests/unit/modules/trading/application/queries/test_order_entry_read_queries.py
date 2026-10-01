"""`EPIC-028O` — the reads the desks size orders with answer from the
addressed venue's own ports. Spot has no leverage, brackets or mark price, so
it answers `NotApplicable` without touching a port; the notional limit is
the one the app's own gate applies."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_best_bid_ask import (
    GetBestBidAskQuery,
    GetBestBidAskQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_futures_symbol_setting import (
    GetFuturesSymbolSettingQuery,
    GetFuturesSymbolSettingQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_leverage_brackets import (
    GetLeverageBracketsQuery,
    GetLeverageBracketsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_mark_price import (
    GetMarkPriceQuery,
    GetMarkPriceQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order_notional_limit import (
    GetOrderNotionalLimitQuery,
    GetOrderNotionalLimitQueryHandler,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_book_ticker_reader import (
    IBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_mark_price_reader import (
    IMarkPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.mark_price import (
    MarkPrice,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.unarranged_venue_ports import (
    UnarrangedAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimits,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET
_SETTING = FuturesSymbolSetting("BTCUSDT", 20, MarginType.CROSSED, Decimal(2_000_000))
_BRACKETS = LeverageBrackets(
    "BTCUSDT",
    (
        LeverageBracket(
            1, 125, Decimal(0), Decimal(50_000), Decimal("0.004"), Decimal(0)
        ),
    ),
)
_MARK = MarkPrice("BTCUSDT", Decimal(64000), datetime(2026, 10, 1, tzinfo=UTC))


class _Control(UnarrangedAccountControl):
    """Answers the two reads; every change still fails the test."""

    def symbol_setting(self, symbol: str) -> FuturesSymbolSetting:
        return replace(_SETTING, symbol=symbol)

    def leverage_brackets(self, symbol: str) -> LeverageBrackets:
        return replace(_BRACKETS, symbol=symbol)


class _Marks(IMarkPriceReader):
    def mark_price(self, symbol: str) -> MarkPrice:
        return replace(_MARK, symbol=symbol)


class _Book(IBookTickerReader):
    def __init__(self, mid: str) -> None:
        self._mid = Decimal(mid)

    def best_bid_ask(self, symbol: str) -> BestBidAsk:
        return BestBidAsk(symbol, self._mid - 1, Decimal(1), self._mid + 1, Decimal(1))


def _contexts() -> FakeVenueContexts:
    return FakeVenueContexts(
        replace(
            fake_venue_context(_FUTURES),
            account_control=_Control(),
            mark_price_reader=_Marks(),
            book_ticker_reader=_Book("64000"),
        ),
        replace(fake_venue_context(_SPOT), book_ticker_reader=_Book("50000")),
    )


def test_futures_answers_its_setting_brackets_and_mark() -> None:
    contexts = _contexts()

    setting = GetFuturesSymbolSettingQueryHandler(contexts).execute(
        GetFuturesSymbolSettingQuery(venue=_FUTURES, symbol="ETHUSDT")
    )
    brackets = GetLeverageBracketsQueryHandler(contexts).execute(
        GetLeverageBracketsQuery(venue=_FUTURES, symbol="ETHUSDT")
    )
    mark = GetMarkPriceQueryHandler(contexts).execute(
        GetMarkPriceQuery(venue=_FUTURES, symbol="ETHUSDT")
    )

    assert setting == replace(_SETTING, symbol="ETHUSDT")
    assert brackets == replace(_BRACKETS, symbol="ETHUSDT")
    assert mark == replace(_MARK, symbol="ETHUSDT")


@pytest.mark.parametrize(
    "ask",
    [
        lambda c: GetFuturesSymbolSettingQueryHandler(c).execute(
            GetFuturesSymbolSettingQuery(venue=_SPOT, symbol="BTCUSDT")
        ),
        lambda c: GetLeverageBracketsQueryHandler(c).execute(
            GetLeverageBracketsQuery(venue=_SPOT, symbol="BTCUSDT")
        ),
        lambda c: GetMarkPriceQueryHandler(c).execute(
            GetMarkPriceQuery(venue=_SPOT, symbol="BTCUSDT")
        ),
    ],
    ids=["setting", "brackets", "mark"],
)
def test_spot_answers_not_applicable_rather_than_a_figure(ask: object) -> None:
    assert ask(_contexts()) is NotApplicable.ON_THIS_VENUE  # type: ignore[operator]


def test_each_venue_answers_from_its_own_book() -> None:
    handler = GetBestBidAskQueryHandler(_contexts())

    futures = handler.execute(GetBestBidAskQuery(venue=_FUTURES, symbol="BTCUSDT"))
    spot = handler.execute(GetBestBidAskQuery(venue=_SPOT, symbol="BTCUSDT"))

    assert (futures.bid_price, futures.ask_price) == (63999, 64001)
    assert (spot.bid_price, spot.ask_price) == (49999, 50001)


@pytest.mark.parametrize("venue", [_FUTURES, _SPOT])
def test_the_notional_limit_is_the_one_the_gate_applies(venue: TradingVenue) -> None:
    policy = TradingLimitPolicy(
        TradingLimits(
            max_orders_per_session=20,
            max_notional_per_order=Decimal(750),
            max_positions_per_symbol=1,
            min_order_interval=timedelta(seconds=60),
        )
    )

    limit = GetOrderNotionalLimitQueryHandler(policy).execute(
        GetOrderNotionalLimitQuery(venue=venue)
    )

    assert limit == Decimal(750)


@pytest.mark.parametrize(
    "build",
    [
        lambda: GetFuturesSymbolSettingQuery(venue=_FUTURES, symbol=""),
        lambda: GetLeverageBracketsQuery(venue=_FUTURES, symbol=""),
        lambda: GetMarkPriceQuery(venue=_FUTURES, symbol=""),
        lambda: GetBestBidAskQuery(venue=_FUTURES, symbol=""),
    ],
    ids=["setting", "brackets", "mark", "book"],
)
def test_an_empty_symbol_is_refused_at_construction(build: object) -> None:
    with pytest.raises(ValueError, match="symbol"):
        build()  # type: ignore[operator]
