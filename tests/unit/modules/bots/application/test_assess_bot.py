"""`EPIC-048B` — `AssessBotQuery` judges a bot the way Start does, from the facts a screen holds.

The business promise, on real-money bots: Start is offered only when nothing is left, and the
screen never offers it on facts nobody has read. The assessment is the Start path's own
(`test_the_screen_and_start_read_the_same_world_the_same_way.py` holds the scenario parity);
here are what the door adds: the Run step waits while its host facts are being read, a bot with a
run is not assessed for Start, and an edit's budget is judged against the host's caps with no read.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.planner_numbers import (
    read_planner_numbers,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.assess_bot import (
    RUN_FACTS_READING,
    AssessBotQuery,
    AssessBotQueryHandler,
    BotAssessment,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_run_facts import (
    GetBotRunFactsQuery,
    GetBotRunFactsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.account_view import (
    account_view_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    ReadinessStep,
    StepStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.connection_read import (
    ConnectionRead,
    ConnectionState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
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


def _assess(
    world: ReadinessWorld,
    *,
    config: Mapping[str, str] = CONFIG,
    read_run_facts: bool = True,
    bot_id: str = BOT,
) -> BotAssessment:
    """The query as the screen sends it: every fact read the way the screen reads it."""
    snapshot = BotSnapshot.of(world.store.load(BotId(bot_id)).bot, None)
    answer = world.account.read(SYMBOL)
    assert isinstance(answer, VenueAccountSnapshot)
    numbers = read_planner_numbers(world.ports, world.caps, snapshot.venue, SYMBOL)
    assert not isinstance(numbers, str)
    run = (
        GetBotRunFactsQueryHandler(world.store, world.ports, world.caps).execute(
            GetBotRunFactsQuery(bot_id, snapshot.venue, SYMBOL)
        )
        if read_run_facts
        else None
    )
    return AssessBotQueryHandler().execute(
        AssessBotQuery(
            snapshot,
            world.kinds.kind("grid"),
            config,
            ConnectionRead(
                ConnectionState.CONNECTED, "Spot Testnet", account_view_of(answer)
            ),
            PlannerMarket(numbers[0], numbers[1], None, None),
            run,
            world.facts.read(world.store.load(BotId(bot_id)).bot),
        )
    )


def test_a_ready_bot_may_start() -> None:
    readiness = _assess(readiness_world()).readiness

    assert readiness is not None
    assert readiness.can_start, readiness.message()


def test_start_waits_while_the_run_facts_are_being_read() -> None:
    """Never a Start judged on facts nobody has read: one item, worded, and the Run step open."""
    readiness = _assess(readiness_world(), read_run_facts=False).readiness

    assert readiness is not None
    assert not readiness.can_start
    assert [item.code for item in readiness.items] == [RUN_FACTS_READING]
    assert readiness.step(ReadinessStep.RUN).status is StepStatus.OPEN
    assert readiness.message() == (
        "1 thing left: Spot Testnet: "
        "Checking the other bots, the symbol's lease and the venue…"
    )


def test_what_the_host_knows_blocks_start() -> None:
    world = readiness_world()
    add_bot(world, "zzz999", S.RUNNING)
    world.session.claim_symbol(SYMBOL, "manual:trade-tab")

    readiness = _assess(world).readiness

    assert readiness is not None
    codes = [item.code for item in readiness.items]
    assert codes == ["RUN_OTHER_BOT_ACTIVE", "RUN_SYMBOL_LEASED"]
    assert "manual:trade-tab" in readiness.message()


def test_a_bot_with_a_run_is_not_assessed_for_start() -> None:
    world = readiness_world()
    add_bot(world, "zzz999", S.RUNNING, symbol="ETHUSDT")

    assessment = _assess(world, bot_id="zzz999")

    assert assessment.readiness is None
    assert assessment.field_verdicts == ()


_TEN_ORDERS = OwnerBudgetCaps(
    max_open_orders=10,
    min_order_spacing=timedelta(milliseconds=100),
    max_orders_per_minute=600,
)


@pytest.mark.parametrize(
    ("grid_count", "refused"),
    [("8", False), ("9", False), ("10", True)],
    ids=["nine-orders", "ten-orders-at-the-cap", "eleven-orders-over"],
)
def test_an_edit_over_the_caps_is_refused_without_a_read(
    grid_count: str, refused: bool
) -> None:
    """Boundary of trading's `max_open_orders`: a Grid keeps `grid_count + 1` orders open, and the
    caps came with the host's Run facts, so the edit is judged where it was typed."""
    world = readiness_world(caps=_TEN_ORDERS)

    readiness = _assess(world, config={**CONFIG, "grid_count": grid_count}).readiness

    assert readiness is not None
    budget = [i for i in readiness.items if i.code == "RUN_BUDGET_REFUSED"]
    assert bool(budget) is refused
    if refused:
        assert budget[0].reason == (
            "The ladder keeps 11 orders open; trading allows at most 10. Use fewer grids"
        )
