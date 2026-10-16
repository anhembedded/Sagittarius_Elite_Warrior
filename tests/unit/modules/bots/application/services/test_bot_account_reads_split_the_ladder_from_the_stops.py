"""`EPIC-039L` (decision D4) - the bot's ladder reads never see its protective stop.

@details One seam: of the open orders that carry the bot's tag, `ladder_orders` are those a
ladder holds and `protective_orders` are those that close the whole position. The stop sequence's
confirmation, the housekeeping, the reconcile and the recovery report all read the ladder through
`BotOrderGateway.tagged_open_orders`; if it answered the stop too, a stop kept under a standing
position would never let the bot be confirmed stopped, and a restart would call it an unknown
tagged order and halt."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_account_reads import (
    BotAccountReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_identity import (
    BotIdentity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_order_gateway import (
    BotOrderGateway,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.working_type import (
    WorkingType,
)

_IDENTITY = BotIdentity("bot.abc123", "abc123", "BTCUSDT")


def _order(suffix: str, tag: str = "abc123", *, stop: bool = False) -> Order:
    return Order(
        client_order_id=ClientOrderId(f"SEW-{tag}-{suffix}"),
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.STOP_MARKET if stop else OrderType.LIMIT,
        quantity=Decimal(0) if stop else Decimal("0.01"),
        price=None if stop else Decimal(65000),
        stop_price=Decimal(60000) if stop else None,
        close_position=stop,
        working_type=WorkingType.MARK_PRICE if stop else WorkingType.LAST_PRICE,
    )


def _ports(*orders: Order) -> Mock:
    ports = Mock()
    ports.account_activity.open_orders.return_value = tuple(orders)
    return ports


_LADDER = _order("0000000001")
_STOP = _order("0000000002", stop=True)
_OTHER_BOTS = _order("0000000003", tag="zzz999")
_OTHER_BOTS_STOP = _order("0000000004", tag="zzz999", stop=True)
_ALL = (_LADDER, _STOP, _OTHER_BOTS, _OTHER_BOTS_STOP)


def test_the_ladder_read_is_the_bots_own_orders_without_its_stop() -> None:
    reads = BotAccountReads(_ports(*_ALL), _IDENTITY)

    assert reads.ladder_orders() == (_LADDER,)


def test_the_stop_read_is_the_bots_own_stops_alone() -> None:
    reads = BotAccountReads(_ports(*_ALL), _IDENTITY)

    assert reads.protective_orders() == (_STOP,)


def test_every_ladder_read_of_the_gateway_goes_through_the_seam() -> None:
    gateway = BotOrderGateway(_ports(*_ALL), _IDENTITY, Mock())

    assert gateway.tagged_open_orders() == (_LADDER,)
    assert gateway.protective_orders() == (_STOP,)
