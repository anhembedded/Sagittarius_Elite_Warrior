"""`BOT-174` — an exchange snapshot a test can start from.

@details A funded Spot Testnet account that holds a little of the base, no open
order on the symbol and nothing left by earlier runs: a test changes the one fact
it is about with `facts(...)`, so every other stays what a working account has.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeFacts,
    ExchangeLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsInventory,
)

READ_AT = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
FUNDED = Decimal(50_000)


def facts(**changes: object) -> ExchangeFacts:
    base = ExchangeFacts(
        venue_title="Spot Testnet",
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        read_at=READ_AT,
        base_free=Decimal("0.5"),
        base_locked=Decimal(0),
        quote_free=FUNDED,
        quote_locked=Decimal(0),
        own_sell_base=Decimal(0),
        own_buy_quote=Decimal(0),
        own_open_orders=0,
        foreign_open_orders=0,
        earlier_runs=EarlierRunsInventory(),
        can_trade=True,
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def loaded(**changes: object) -> ExchangeLoaded:
    return ExchangeLoaded(facts(**changes))
