"""`EPIC-039G` - what a Futures account is charged, end to end on the fake exchange.

@details The composed app over the Futures testnet: the commission and realized profit of
a fill arrive on `OrderFilledEvent` through the stream's own parser, a funding settlement
arrives as `FundingChargedEvent`, and the funding rate is read through the venue's order
entry terms. The rates are the fake's (maker 0.02 %); where Binance's pages are silent the
choice is the fake's, stated in `tests/sanity/fake_exchange/`."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.funding_charged_event import (
    FundingChargedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.funding_rate import (
    FundingRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .futures_fake_exchange import FUTURES, SYMBOL, booted_futures
from .grid_fake_exchange import FakeExchange
from .test_a_futures_ladder_fills_on_the_fake_exchange import _limit

_EIGHT_HOURS_MS = 8 * 60 * 60 * 1000


def test_a_fill_reports_its_commission_and_the_closing_fill_its_realized_profit(
    futures: FakeExchange,
) -> None:
    with booted_futures(futures) as app:
        fills: list[OrderFilledEvent] = []
        app.engine.context.container.resolve(IEventBus).on(
            OrderFilledEvent, fills.append
        )
        _limit(app, "SEW-c1", OrderSide.BUY, "63000.0", "0.010")
        app.move_price(Decimal(63000))
        _limit(app, "SEW-c2", OrderSide.SELL, "64000.0", "0.010", reduce_only=True)
        app.move_price(Decimal(64000))

        opening, closing = fills

        assert opening.fee_asset == "USDT"
        assert opening.fee_amount == Decimal("0.010") * Decimal(63000) * Decimal(
            "0.0002"
        )
        assert opening.realized_profit == 0, "an opening trade realizes nothing"
        assert closing.fee_amount == Decimal("0.010") * Decimal(64000) * Decimal(
            "0.0002"
        )
        assert closing.realized_profit == Decimal(10), "(64000 - 63000) x 0.010"


def test_a_funding_settlement_reaches_the_app_as_a_charge_on_the_symbol(
    futures: FakeExchange,
) -> None:
    book = futures.urls.futures_book
    book.set_funding_rate(SYMBOL, Decimal("0.0001"))
    with booted_futures(futures) as app:
        charges: list[FundingChargedEvent] = []
        app.engine.context.container.resolve(IEventBus).on(
            FundingChargedEvent, charges.append
        )
        _limit(app, "SEW-c3", OrderSide.BUY, "63000.0", "0.010")
        app.move_price(Decimal(63000))

        book.advance_clock(_EIGHT_HOURS_MS)
        app.deliver()

        (charge,) = charges
        assert charge.symbol == SYMBOL
        assert charge.amount < 0, "a long pays a positive rate"
        assert abs(charge.amount) == Decimal("0.010") * Decimal(63000) * Decimal(
            "0.0001"
        )


def test_the_funding_rate_is_read_through_the_venue_terms(
    futures: FakeExchange,
) -> None:
    futures.urls.futures_book.set_funding_rate(SYMBOL, Decimal("-0.0003"))
    with booted_futures(futures) as app:
        ports = app.engine.context.container.resolve(IVenueTradingPorts)
        rate = ports.get(FUTURES).order_entry_terms.funding_rate_for(SYMBOL)

        assert isinstance(rate, FundingRate)
        assert rate.rate == Decimal("-0.0003")
        assert rate.next_funding_at > rate.as_of
