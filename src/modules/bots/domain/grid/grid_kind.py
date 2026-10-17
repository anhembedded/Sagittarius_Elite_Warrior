"""`EPIC-029C` — Grid as a bot kind (ADR D2): `IBotKind` over the planner.

`validate` and `overlay` delegate to `evaluate_grid` and `grid_overlay`;
nothing is computed here.
The executor factory is given to the kind, not built by it: the executor is
`EPIC-029E`'s, and the kind is constructed where that factory exists.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    IBotExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    FUTURES_MARKETS,
    SPOT_MARKETS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_overlay import (
    GridOverlaySource,
    grid_overlay,
    liquidation_marks,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_parameter_check import (
    grid_parameter_problem,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    RecoveryLayer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict

GRID_KIND_ID = "grid"

#: The markets a Grid runs on (`EPIC-039H`): the one declaration every Grid-specific caller
#: of `bot_profile_of` passes and `GridKind.supported_profiles` answers.
GRID_MARKETS: frozenset[MarketType] = SPOT_MARKETS | FUTURES_MARKETS


#: The Grid's layer of the halt-recovery policy (`EPIC-042`). Empty today: the Grid recovers the
#: common reasons only. `rate_limited` joins it when `EPIC-042F` moves the rate-limit resume
#: onto the mechanism (until then `GridRateLimitPause` owns that reason).
GRID_RECOVERY_LAYER = RecoveryLayer(GRID_KIND_ID)


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

    def supported_profiles(self) -> frozenset[MarketType]:
        return GRID_MARKETS

    def recovery_layer(self) -> RecoveryLayer:
        return GRID_RECOVERY_LAYER

    def validate(self, inputs: BotKindInputs) -> tuple[Verdict, ...]:
        return evaluate_grid(inputs, self._thresholds).verdicts

    def parameter_problem(
        self, config: Mapping[str, str], changed: Collection[str]
    ) -> str | None:
        return grid_parameter_problem(config, changed)

    def overlay(self, inputs: BotKindInputs) -> BotOverlay:
        """The planner preview's overlay: the plan, its range and exits, and
        the ATR zones when the market view has a daily ATR (`grid_overlay`)."""
        evaluation = evaluate_grid(inputs, self._thresholds)
        if evaluation.plan is None or evaluation.params is None:
            return BotOverlay()
        return grid_overlay(
            GridOverlaySource(
                evaluation.params,
                evaluation.plan,
                self._thresholds,
                daily_atr=inputs.market.daily_atr,
                liquidations=liquidation_marks(evaluation.verdicts),
            )
        )

    def executor_factory(self) -> IBotExecutorFactory:
        return self._executor_factory
