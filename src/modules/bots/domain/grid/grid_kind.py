"""`EPIC-029C` — Grid as a bot kind (ADR D2): `IBotKind` over the planner.

`validate` and `overlay` delegate to `evaluate_grid`; nothing is computed here.
The executor factory is given to the kind, not built by it: the executor is
`EPIC-029E`'s, and the kind is constructed where that factory exists.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    IBotExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import (
    BotOverlay,
    OverlayLine,
    OverlayRole,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import LevelSide
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict

GRID_KIND_ID = "grid"

_LEVEL_ROLES = {
    LevelSide.BUY: OverlayRole.BUY_LEVEL,
    LevelSide.SELL: OverlayRole.SELL_LEVEL,
    LevelSide.EMPTY: OverlayRole.EMPTY_LEVEL,
}


class GridKind(IBotKind):
    """A ladder of resting orders across a price range."""

    def __init__(
        self, executor_factory: IBotExecutorFactory, thresholds: GridThresholds
    ) -> None:
        self._executor_factory = executor_factory
        self._thresholds = thresholds

    @property
    def kind_id(self) -> str:
        return GRID_KIND_ID

    def validate(self, inputs: BotKindInputs) -> tuple[Verdict, ...]:
        return evaluate_grid(inputs, self._thresholds).verdicts

    def overlay(self, inputs: BotKindInputs) -> BotOverlay:
        evaluation = evaluate_grid(inputs, self._thresholds)
        if evaluation.plan is None or evaluation.params is None:
            return BotOverlay()
        lines = [
            OverlayLine(level.price, _LEVEL_ROLES[level.side], f"L{level.index}")
            for level in evaluation.plan.levels
        ]
        stop = evaluation.params.stop_loss_price
        if stop is not None:
            lines.append(OverlayLine(stop, OverlayRole.STOP_LOSS, "SL"))
        target = evaluation.params.take_profit_price
        if target is not None:
            lines.append(OverlayLine(target, OverlayRole.TAKE_PROFIT, "TP"))
        return BotOverlay(tuple(sorted(lines, key=lambda line: line.price)))

    def executor_factory(self) -> IBotExecutorFactory:
        return self._executor_factory
