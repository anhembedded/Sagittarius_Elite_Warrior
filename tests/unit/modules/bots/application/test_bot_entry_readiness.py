"""`EPIC-044B` - the readiness a waiting Grid asks at the price that enters its range.

`BotEntryReadiness` judges a bot that already waits (its own state is AWAITING_RANGE) with the
assessment the Bots screen and Start read. A refusal of the plan halts the bot; a refusal that is
only the state of the world (the venue could not be read, a bot of the venue is still RECOVERING,
the symbol is held for the moment) passes by itself and keeps it waiting (review of #682, ADR 044
D5). Each class is decided here over the real assessment's output, not a scripted one.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_entry_readiness import (
    BotEntryReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_entry_readiness import (
    EntryReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    ReadinessWorld,
    add_bot,
    failing,
    readiness_world,
    set_available,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
)

S = BotLifecycleState


def _waiting() -> ReadinessWorld:
    world = readiness_world()
    add_bot(world, BOT, S.AWAITING_RANGE)
    return world


def _judge(world: ReadinessWorld) -> EntryReadiness:
    bot = world.store.load(BotId(BOT)).bot
    return BotEntryReadiness(world.reader).judge(bot)


def test_a_funded_waiting_bot_is_ready_to_lay() -> None:
    assert _judge(_waiting()).ready


def test_a_balance_too_small_for_the_ladder_is_a_refusal_of_the_plan() -> None:
    world = _waiting()
    set_available(world, Decimal(10))

    judged = _judge(world)

    assert not judged.ready
    assert not judged.transient, "no wait will fund the ladder: the bot halts"
    assert judged.refusal


@pytest.mark.parametrize(
    "other",
    [
        pytest.param(("bbbbbb", S.RECOVERING, "ETHUSDT"), id="venue-recovering"),
        pytest.param(("bbbbbb", S.RUNNING, None), id="symbol-held-by-another-bot"),
    ],
)
def test_the_state_of_the_world_keeps_the_bot_waiting(
    other: tuple[str, BotLifecycleState, str | None],
) -> None:
    """A restart resumes its RECOVERING bots one after another; until the last is back the
    venue is not ready for a bot to start, and a waiting bot must not halt for that."""
    world = _waiting()
    bot_id, state, symbol = other
    if symbol is None:
        add_bot(world, bot_id, state)
    else:
        add_bot(world, bot_id, state, symbol=symbol)

    judged = _judge(world)

    assert not judged.ready
    assert judged.transient


def test_an_account_that_could_not_be_read_keeps_the_bot_waiting() -> None:
    world = _waiting()
    failing(
        world,
        ConnectFailure(
            AccountSource.SPOT_TESTNET, ConnectionFailureKind.MAINTENANCE, "the account"
        ),
    )

    judged = _judge(world)

    assert not judged.ready
    assert judged.transient
