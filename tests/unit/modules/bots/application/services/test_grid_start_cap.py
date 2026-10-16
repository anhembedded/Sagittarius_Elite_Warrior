"""`EPIC-039I` - the start sequence refuses an order above trading's cap before any opening.

@details The Plan's verdict already refuses a ladder whose orders are worth more than the cap
(`check_max_notional`), so Start is usually refused before the executor runs. The sequence repeats
the judgement with the same sizing (`grid_order_sizing.find_cap_breach`) for a plan that reaches it
anyway, as `BUG-212` did for the minimum: an untested guard on real money is not one.
"""

from __future__ import annotations

from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.protection_spot import (
    NoProtection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.start.grid_start_sequence import (
    GridStartSequence,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.order_flags_futures import (
    PositionOrderFlags,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_opening_strategy import (
    IOpeningStrategy,
    OpeningResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    ExposureLimits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    LevelSizing,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    CAP,
    CONFIG,
    LAST_PRICE,
    GridWorld,
    grid_world,
)

_POSITION = ExposureLimits(frozenset(TradeDirection), 125, ExposureKind.POSITION)


class _Opening(IOpeningStrategy):
    def __init__(self) -> None:
        self.opened = 0

    def open(self, plan: GridPlan) -> OpeningResult:
        self.opened += 1
        return OpeningResult(None)


def _sequence(world: GridWorld, opening: IOpeningStrategy) -> GridStartSequence:
    context = replace(world.executor._context, limits=_POSITION)
    return GridStartSequence(
        context, opening, PositionOrderFlags(TradeDirection.LONG), NoProtection()
    )


def _ladder(world: GridWorld, leverage: str) -> GridPlan:
    config = {**CONFIG, "direction": "LONG", "leverage": leverage}
    return plan(
        GridParams.from_config(config),
        world.executor._context.terms,
        LAST_PRICE,
        LevelSizing.EQUAL_QUANTITY,
    )


def test_an_order_above_the_cap_is_refused_before_the_opening_is_asked() -> None:
    world = grid_world(state=BotLifecycleState.STARTING)
    opening = _Opening()
    ladder = _ladder(world, "2")
    assert max(lv.notional for lv in ladder.order_levels) > CAP, (
        "the case must exceed it"
    )

    _sequence(world, opening).run(ladder)

    assert opening.opened == 0
    assert world.runtime().reason is GridReason.START_REFUSED
    assert f"above trading's cap of {CAP}" in world.runtime().reason_detail
    assert world.book.requests == []


def test_a_ladder_within_the_cap_goes_on_to_the_opening() -> None:
    world = grid_world(state=BotLifecycleState.STARTING)
    opening = _Opening()
    ladder = _ladder(world, "1")
    assert max(lv.notional for lv in ladder.order_levels) <= CAP

    _sequence(world, opening).run(ladder)

    assert opening.opened == 1
