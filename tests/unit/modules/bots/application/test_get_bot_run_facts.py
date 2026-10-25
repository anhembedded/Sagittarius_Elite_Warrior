"""`EPIC-048B` — `GetBotRunFactsQuery` answers the Run facts the Bots screen read itself.

The business promise: the facts a screen judges a Start by are the host's (which bots hold the
symbol or fill the venue, who holds the lease, whether the venue is on), read through the query,
and the budget of the parameters on screen is judged from the caps the query carries, so an edit
is re-judged without a read. In one world, the query's facts with that budget equal what the
Start path's reader reads, scenario by scenario.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_run_facts import (
    GetBotRunFactsQuery,
    GetBotRunFactsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.other_active_bot import (
    BotSlot,
    occupancy_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_run_facts import (
    BotRunFactsReader,
    run_facts_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_facts import RunFacts
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    ReadinessWorld,
    add_bot,
    readiness_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
    SYMBOL,
)

_VENUE = TradingVenue.SPOT_TESTNET


def _query(world: ReadinessWorld) -> GetBotRunFactsQueryHandler:
    return GetBotRunFactsQueryHandler(world.store, world.ports, world.caps)


def _through_the_query(world: ReadinessWorld, config: dict[str, str]) -> RunFacts:
    host = _query(world).execute(GetBotRunFactsQuery(BOT, _VENUE, SYMBOL))
    return run_facts_for(host, config)


def _as_start_reads_them(world: ReadinessWorld, config: dict[str, str]) -> RunFacts:
    reading = world.store.load_all()
    return BotRunFactsReader(world.ports, world.caps).read(
        BOT,
        _VENUE,
        SYMBOL,
        config,
        occupancy_of(
            BOT,
            _VENUE,
            SYMBOL,
            (
                BotSlot(
                    s.bot.bot_id.value,
                    s.bot.definition.venue,
                    s.bot.definition.symbol,
                    s.bot.state,
                )
                for s in reading.bots
            ),
            (refused.name for refused in reading.refused),
        ),
    )


SCENARIOS: dict[str, Callable[[ReadinessWorld], None]] = {
    "nothing in the way": lambda world: None,
    "another bot is active on the symbol": lambda world: add_bot(
        world, "zzz999", S.RUNNING
    ),
    "the other bot also holds the lease": lambda world: (
        add_bot(world, "zzz999", S.RUNNING),
        world.session.claim_symbol(SYMBOL, "bot.zzz999"),
    ),
    "a strategy holds the symbol": lambda world: world.session.claim_symbol(
        SYMBOL, "strategy.1"
    ),
    "the bot's own lease": lambda world: world.session.claim_symbol(
        SYMBOL, f"bot.{BOT}"
    ),
    "a bot on the venue waits to recover": lambda world: add_bot(
        world, "zzz999", S.RECOVERING, symbol="ETHUSDT"
    ),
    "a refused file counts as active": lambda world: world.store.refuse_file(
        BotId("qqq888"), "bad json"
    ),
}


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_query_reads_the_facts_start_reads(scenario: str) -> None:
    world = readiness_world()
    SCENARIOS[scenario](world)

    assert _through_the_query(world, CONFIG) == _as_start_reads_them(world, CONFIG)


def test_the_scenarios_are_not_all_the_same_facts() -> None:
    answers = set()
    for apply in SCENARIOS.values():
        world = readiness_world()
        apply(world)
        answers.add(_through_the_query(world, CONFIG))

    assert len(answers) >= 5


def test_a_venue_that_is_not_on_is_named_and_reads_no_lease() -> None:
    world = readiness_world(venue=TradingVenue.SPOT_MAINNET, bot_venue=_VENUE)
    world.session.claim_symbol(SYMBOL, "strategy.1")

    facts = _through_the_query(world, CONFIG)

    assert facts.venue_problem == "Spot Testnet is not enabled"
    assert facts.lease_holder == ""


def test_the_query_carries_the_caps_and_judges_no_budget() -> None:
    """The budget is the parameters' on screen, which the host does not have."""
    caps = OwnerBudgetCaps(
        max_open_orders=5,
        max_orders_per_minute=60,
        min_order_spacing=readiness_world().caps.min_order_spacing,
    )
    world = readiness_world(caps=caps)

    host = _query(world).execute(GetBotRunFactsQuery(BOT, _VENUE, SYMBOL))

    assert host.caps == caps
    assert host.facts.budget_problem == ""


@pytest.mark.parametrize(
    ("grid_count", "refused"),
    [("9", False), ("10", True)],
    ids=["ten-orders-fit", "eleven-orders-exceed"],
)
def test_an_edit_is_judged_against_the_caps_without_a_read(
    grid_count: str, refused: bool
) -> None:
    """Boundary of `max_open_orders`: a Grid keeps `grid_count + 1` orders open."""
    caps = OwnerBudgetCaps(
        max_open_orders=10,
        max_orders_per_minute=60,
        min_order_spacing=readiness_world().caps.min_order_spacing,
    )
    world = readiness_world(caps=caps)
    host = _query(world).execute(GetBotRunFactsQuery(BOT, _VENUE, SYMBOL))
    edited = {**CONFIG, "grid_count": grid_count}

    facts = run_facts_for(host, edited)

    assert bool(facts.budget_problem) is refused
    assert facts == _as_start_reads_them(world, edited)
