"""The report's worked example (PRO-006 §1.5): BTC at 65,000, 10,000 USDT,
60,000–70,000, 10 grids, a 0.1% fee — and helpers to vary one field of it."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    ExchangeTerms,
    MarketView,
)

LAST_PRICE = Decimal(65000)

#: BTCUSDT-like filters, with a step fine enough not to blur the report's numbers.
TERMS = ExchangeTerms(
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.00000001"),
    min_notional=Decimal(5),
    maker_fee=Decimal("0.001"),
    taker_fee=Decimal("0.001"),
    max_notional_per_order=Decimal(5000),
    max_open_orders=100,
)

CONFIG: dict[str, str] = {
    "lower": "60000",
    "upper": "70000",
    "grid_count": "10",
    "spacing": "ARITHMETIC",
    "capital_quote": "10000",
    "stop_loss": "percent:5",
    "take_profit": "percent:5",
}


def inputs(
    terms: ExchangeTerms = TERMS,
    last_price: Decimal = LAST_PRICE,
    daily_atr: Decimal | None = None,
    foreign_open_orders: int | None = None,
    **changes: str,
) -> BotKindInputs:
    return BotKindInputs(
        {**CONFIG, **changes},
        terms,
        MarketView(last_price, daily_atr, foreign_open_orders),
    )
