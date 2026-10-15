"""`EPIC-039B` review - a Spot definition that names a leverage is never traded at it.

The parameters a plan file or a screen saves are the user's and are kept as written; they are
judged when the bot is made ready, and a leverage above what the venue's profile allows is
refused there, in words, not clamped to 1. These tests drive the same definition through the
plan applier (which stores it untouched) and through the readiness gate Start uses.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    BotPlanDocument,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_applier import (
    PlanApplier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_differ import (
    PrunePolicy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.readiness_assessment import (
    ConnectionRead,
    ConnectionState,
    ReadinessInputs,
    RunFacts,
    assess_readiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    SPOT_PROFILE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    CommandWorld,
    MemoryAppliedPlanStore,
    planned,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    TERMS,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    inputs as grid_inputs,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.exchange_facts_fixtures import (
    loaded,
)

_KIND = GridKind(None, GridThresholds())  # type: ignore[arg-type]
_MARKET = PlannerMarket(TERMS, grid_inputs().market, None, None)
_CONNECTED = ConnectionRead(
    ConnectionState.CONNECTED,
    "Spot Testnet",
    AccountView(Decimal(50_000), "USDT", True, "Spot Testnet"),
)


def _readiness(config: dict[str, str]):
    return assess_readiness(
        ReadinessInputs(
            kind=_KIND,
            kind_id="grid",
            symbol="BTCUSDT",
            config=config,
            connection=_CONNECTED,
            market=_MARKET,
            run=RunFacts(),
            exchange=loaded(),
            profile=SPOT_PROFILE,
        )
    )


def test_a_plan_with_a_spot_leverage_is_stored_as_written_and_refused_at_start() -> (
    None
):
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    entry = planned(params={**CONFIG, "direction": "LONG", "leverage": "3"})

    PlanApplier(world, store).apply(BotPlanDocument((entry,)), PrunePolicy.KEEP)

    (stored,) = [s.bot for s in world.store.load_all().bots]
    assert stored.definition.config["leverage"] == "3", "kept as the user wrote it"
    readiness = _readiness(dict(stored.definition.config))
    assert not readiness.can_start
    items = [i for i in readiness.items if i.code == "LEVERAGE_NOT_ALLOWED"]
    assert len(items) == 1
    assert items[0].refusal is BotRefusal.PARAMETERS_REFUSED


def test_a_spot_leverage_of_one_leaves_nothing_to_fix() -> None:
    readiness = _readiness({**CONFIG, "direction": "LONG", "leverage": "1"})

    assert readiness.can_start
