"""`BUG-259` — a start refuses a symbol whose orders another owner's tag holds.

Each data root enforces "one active bot per symbol" only for itself. A second copy of the app (a
VPS host, a second desktop) on the same account trades the same symbol; in one-way mode Binance
nets both bots into one position, and a close-position stop of one closes both. The account's open
orders carry the other bot's tag (`SEW-<tag>-...`), a tag no bot of this data root holds: the start
says so in words and places nothing. Red before: the start went through and laid its ladder beside
the other owner's.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    SYMBOL,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.start_world import (
    StartWorld,
    start_world,
)

S = BotLifecycleState
_OTHER = "y3embt"


def _bot(world: StartWorld) -> Bot:
    return world.store.load(BotId(BOT)).bot


def _rests(world: StartWorld, client_order_id: str, symbol: str = SYMBOL) -> None:
    world.book.open[client_order_id] = Order(
        ClientOrderId(client_order_id),
        symbol,
        OrderSide.BUY,
        OrderType.LIMIT,
        Decimal("0.1"),
        price=Decimal(100),
    )


def test_another_owners_tagged_order_on_the_symbol_refuses_the_start() -> None:
    world = start_world()
    _rests(world, f"SEW-{_OTHER}-0123456789")

    refusal = world.preconditions.check(_bot(world), world.clock.now())

    assert refusal is not None
    assert refusal.refusal is BotRefusal.VENUE_NOT_READY
    assert _OTHER in refusal.message
    assert SYMBOL in refusal.message
    assert world.session.budgets == {}
    assert world.session.claim_symbol(SYMBOL, "manual"), "no lease was left behind"
    assert world.session.ready_requests == 0, "a refused start opens nothing"


def test_the_runner_leaves_the_bot_as_it_was_when_the_start_is_refused() -> None:
    world = start_world()
    _rests(world, f"SEW-{_OTHER}-0123456789")

    result = world.runner.start(BOT)

    assert not result.accepted
    assert _bot(world).state is S.DRAFT
    assert world.book.requests == []


def test_a_tag_of_another_bot_in_this_data_root_is_not_another_owner() -> None:
    """A sibling of this data root (RECOVERING, or stopped with an order left) is known."""
    world = start_world()
    sibling = Bot.draft(BotId("sib001"), _bot(world).definition, world.clock.now())
    _rests(world, "SEW-sib001-0123456789")

    refusal = world.preconditions.check(
        _bot(world), world.clock.now(), venue_bots=(sibling,)
    )

    assert refusal is None


def test_an_order_without_a_bot_tag_is_not_another_bots() -> None:
    world = start_world()
    _rests(world, "SEW-0123456789ab")

    assert world.preconditions.check(_bot(world), world.clock.now()) is None
