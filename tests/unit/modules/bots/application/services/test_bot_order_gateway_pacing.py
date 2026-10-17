"""`EPIC-029J1b` — the venue's order pacer paces what builds a ladder, never what protects a position.

The pacer is shared by every bot of a venue, so a turn can queue behind a neighbour's whole ladder
(five bots resuming together: about 100 orders at 250 ms, 25 s). A protective stop or a close that
waited in that queue would leave a leveraged position bare for as long. The ladder's orders and the
openings take a turn; the exits do not.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_order_gateway import (
    BotIdentity,
    BotOrderGateway,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.protective_stop_request import (
    ProtectiveStopOrder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world_doubles import (
    CountingPacer,
)

D = Decimal


def _gateway() -> tuple[BotOrderGateway, CountingPacer]:
    pacer = CountingPacer()
    gateway = BotOrderGateway(
        Mock(), BotIdentity("bot.abc123", "abc123", "BTCUSDT"), pacer
    )
    return gateway, pacer


@pytest.mark.parametrize(
    "send",
    [
        lambda g: g.place_limit(OrderSide.BUY, D(100), D(1)),
        lambda g: g.market_buy(D(100), D(100)),
        lambda g: g.market_base(OrderSide.BUY, D(1), D(100)),
    ],
    ids=["ladder level", "spot opening", "position opening"],
)
def test_what_builds_a_ladder_takes_a_turn_on_the_venues_pacer(send) -> None:
    gateway, pacer = _gateway()

    send(gateway)

    assert pacer.turns == 1


@pytest.mark.parametrize(
    "send",
    [
        lambda g: g.market_sell(D(1), D(100)),
        lambda g: g.market_reduce_only(OrderSide.SELL, D(1), D(100)),
        lambda g: g.place_protective_stop(
            ProtectiveStopOrder(
                generate_client_order_id("abc123"), OrderSide.SELL, D(50000), D(64000)
            )
        ),
    ],
    ids=["spot exit", "reduce-only close", "protective stop"],
)
def test_an_exit_never_waits_behind_the_neighbours_ladders(send) -> None:
    gateway, pacer = _gateway()

    send(gateway)

    assert pacer.turns == 0
