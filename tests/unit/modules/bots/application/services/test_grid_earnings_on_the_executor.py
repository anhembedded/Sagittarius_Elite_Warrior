"""`EPIC-035M` (L2) — the real executor books BNB-paid fees and keeps the bot's own price.

A fee paid in BNB was dropped from the cost basis and from a cycle's profit, so the
profit was overstated for an account that pays fees in BNB. The fee is converted to
the quote asset at the fill's time, from the BNB market; one that cannot be priced
is counted, never guessed. The bot's last price is saved (at most every 30 s of its
own clock) so the unrealised PnL is judged on the price the bot heard.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_price_reaction import (
    MARK_PRICE_SAVE_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)

_BNB_PRICE = Decimal(600)


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    return world


def _bnb_market(world: GridWorld) -> None:
    world.terms.quote(
        BestBidAsk("BNBUSDT", _BNB_PRICE, Decimal(1), _BNB_PRICE, Decimal(1))
    )


def _fill_paying_bnb(world: GridWorld, price: Decimal, bnb: str) -> None:
    order = world.book.open[world.open_ids_by_price()[price]]
    world.book.open.pop(order.client_order_id)
    world.executor.facts.on_fill(
        BotOrderFill(
            order.client_order_id,
            order.side,
            price,
            order.quantity,
            Decimal(bnb),
            "BNB",
        )
    )


def test_bnb_fees_reduce_the_profit() -> None:
    world = _running()
    _bnb_market(world)

    _fill_paying_bnb(world, Decimal(110), "0.01")

    runtime = world.runtime()
    assert runtime.unpriced_fees == 0
    buy_level = next(l for l in runtime.levels if l.price == Decimal(120))
    assert buy_level.order is not None
    assert buy_level.order.paired_buy_fee_quote == Decimal(6), "0.01 BNB at 600"


def test_a_fee_in_an_asset_that_cannot_be_priced_is_counted_not_guessed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = _running()

    with caplog.at_level(logging.WARNING, logger="App.Bots.GridExecutor"):
        _fill_paying_bnb(world, Decimal(110), "0.01")

    assert world.runtime().unpriced_fees == 1
    assert any("[unpriced-fee]" in record.getMessage() for record in caplog.records)


def test_the_bots_own_price_is_saved_and_only_every_so_often() -> None:
    world = _running()

    world.executor.facts.on_tick(PriceTick.at(Decimal(121)))
    assert world.runtime().mark_price == Decimal(121)

    world.monotonic.advance(MARK_PRICE_SAVE_SECONDS / 2)
    world.executor.facts.on_tick(PriceTick.at(Decimal(122)))
    assert world.runtime().mark_price == Decimal(121), "saved less than 30 s ago"

    world.monotonic.advance(MARK_PRICE_SAVE_SECONDS)
    world.executor.facts.on_tick(PriceTick.at(Decimal(123)))
    runtime = world.runtime()
    assert runtime.mark_price == Decimal(123)
    assert runtime.mark_price_at == world.clock.now()
