"""`EPIC-034H` — in one world, the Bots screen's detail and Start's reader list
the same items.

The screen assembles its inputs from what it holds (the Connect step's account,
the planner's market numbers, the host's Run facts through `GetBotRunFactsQuery`,
the exchange snapshot of `BOT-174`) and judges them through `AssessBotQuery`
(`EPIC-048B`); Start reads them afresh. The
inputs are built apart, the judgement is one function, so a scenario fed to both
must agree: a difference is an input one of them builds differently.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.planner_numbers import (
    read_planner_numbers,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.assess_bot import (
    AssessBotQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_run_facts import (
    GetBotRunFactsQuery,
    GetBotRunFactsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.other_active_bot import (
    VenueOccupancy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_run_facts import (
    BotRunFactsReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.readiness_assessment import (
    ConnectionRead,
    ConnectionState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.account_view import (
    account_view_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_detail import (
    DetailInputs,
    detail_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    ReadinessWorld,
    add_bot,
    readiness_world,
    set_available,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    SYMBOL,
)


def _screens_items(world: ReadinessWorld) -> list[str]:
    """What the Bots screen would list: inputs assembled from what it holds."""
    stored = world.store.load(BotId(BOT))
    snapshot = BotSnapshot.of(stored.bot, None)
    answer = world.account.read(SYMBOL)
    assert isinstance(answer, VenueAccountSnapshot)
    numbers = read_planner_numbers(
        world.ports, world.caps, snapshot.venue, snapshot.symbol
    )
    assert not isinstance(numbers, str)
    # The screen's own door to the host's Run facts (`EPIC-048B`).
    run = GetBotRunFactsQueryHandler(world.store, world.ports, world.caps).execute(
        GetBotRunFactsQuery(BOT, snapshot.venue, snapshot.symbol)
    )
    detail = detail_for(
        DetailInputs(
            snapshot,
            world.kinds.kind("grid"),
            PlannerMarket(numbers[0], numbers[1], None, None),
            world.clock.now(),
            None,
            ConnectionRead(
                ConnectionState.CONNECTED, "Spot Testnet", account_view_of(answer)
            ),
            run,
            world.facts.read(stored.bot),
        ),
        AssessBotQueryHandler().execute,
    )
    assert detail.readiness is not None
    return [item.code for item in detail.readiness.items]


def _starts_items(world: ReadinessWorld) -> list[str]:
    bot = world.store.load(BotId(BOT)).bot
    return [item.code for item in world.reader.read(bot).items]


def _poor(world: ReadinessWorld) -> None:
    set_available(world, Decimal(10))


def _active_and_leased(world: ReadinessWorld) -> None:
    add_bot(world, "zzz999", S.RUNNING)
    world.session.claim_symbol(SYMBOL, "bot.zzz999")


SCENARIOS: dict[str, Callable[[ReadinessWorld], None]] = {
    "ready": lambda world: None,
    "capital above the balance": _poor,
    "another bot is active": lambda world: add_bot(world, "zzz999", S.RUNNING),
    "a bot on another venue is active": lambda world: add_bot(
        world, "zzz999", S.RUNNING, venue=TradingVenue.FUTURES_TESTNET
    ),
    "a bot on another symbol of the venue is active": lambda world: add_bot(
        world, "zzz999", S.RUNNING, symbol="ETHUSDT"
    ),
    "another bot is active and holds the lease": _active_and_leased,
    "a bot on the venue is waiting to recover": lambda world: add_bot(
        world, "zzz999", S.RECOVERING, symbol="ETHUSDT"
    ),
    "the symbol is leased": lambda world: world.session.claim_symbol(
        SYMBOL, "strategy.1"
    ),
    "the bots own lease": lambda world: world.session.claim_symbol(
        SYMBOL, f"bot.{BOT}"
    ),
    "a refused file counts as active": lambda world: world.store.refuse_file(
        BotId("qqq888"), "bad json"
    ),
}


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_screen_and_start_list_the_same_items(scenario: str) -> None:
    world = readiness_world()
    SCENARIOS[scenario](world)

    assert _screens_items(world) == _starts_items(world)


def test_the_scenarios_are_not_all_the_same_answer() -> None:
    answers = set()
    for apply in SCENARIOS.values():
        world = readiness_world()
        apply(world)
        answers.add(tuple(_starts_items(world)))

    assert len(answers) >= 4


def test_the_plan_judges_with_the_limits_a_bot_runs_with() -> None:
    """`EPIC-039I` review: the bot's Plan is judged against what a bot may run
    (`exposure_limits_of`), not what the market allows a plan to name, so a saved definition
    that names a direction no bot runs shows a refused Plan and not a passing one that Start then
    refuses. Every direction runs on Futures now, so the case here is a NEUTRAL one the Plan
    accepts; a Spot-only kind on a Futures venue is judged by Spot's limits (the same function)."""
    world = readiness_world()
    stored = world.store.load(BotId(BOT))
    futures = replace(
        stored.bot.definition,
        venue=TradingVenue.FUTURES_TESTNET,
        config={
            **stored.bot.definition.config,
            "direction": "NEUTRAL",
            "leverage": "2",
        },
    )
    snapshot = BotSnapshot.of(
        Bot(stored.bot.bot_id, futures, stored.bot.lifecycle, stored.bot.created_at),
        None,
    )
    # The world's market numbers are the Spot venue's; the judgement under test is the limits.
    numbers = read_planner_numbers(
        world.ports, world.caps, stored.bot.definition.venue, snapshot.symbol
    )
    assert not isinstance(numbers, str)

    detail = detail_for(
        DetailInputs(
            snapshot,
            world.kinds.kind("grid"),
            PlannerMarket(numbers[0], numbers[1], None, None),
            world.clock.now(),
            None,
            ConnectionRead(ConnectionState.READING, ""),
            BotRunFactsReader(world.ports, world.caps).host_facts(
                BOT, snapshot.venue, snapshot.symbol, VenueOccupancy()
            ),
            world.facts.read(stored.bot),
        ),
        AssessBotQueryHandler().execute,
    )

    assert "DIRECTION_NOT_ALLOWED" not in [v.code for v in detail.verdicts]


def test_a_bot_on_another_symbol_of_the_venue_blocks_nothing() -> None:
    """`EPIC-029J` J1b: the symbol, not the venue, is what two bots cannot share."""
    ready = readiness_world()
    other_symbol = readiness_world()
    add_bot(other_symbol, "zzz999", S.RUNNING, symbol="ETHUSDT")

    assert _starts_items(other_symbol) == _starts_items(ready)


def test_the_holder_of_the_symbol_is_named_once_not_as_a_bot_and_again_as_a_lease() -> (
    None
):
    """The active bot on the symbol is also the lease's holder: one cause, one item."""
    world = readiness_world()
    _active_and_leased(world)

    assert _starts_items(world) == ["RUN_OTHER_BOT_ACTIVE"]
    assert _screens_items(world) == ["RUN_OTHER_BOT_ACTIVE"]
