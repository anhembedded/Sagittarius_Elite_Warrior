"""`EPIC-029C` — Grid as a bot kind (ADR D2): `IBotKind` over the planner.

`validate` and `overlay` delegate to `evaluate_grid` and `grid_overlay`;
nothing is computed here.
The executor factory and the backtester are given to the kind, not built by it: the executor is
`EPIC-029E`'s and the backtester `EPIC-040B`'s, and the kind is constructed where they exist.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    IBotExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    IKindBacktester,
)
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
    PAUSE_RULE,
    RATE_LIMITED,
    RecoveryLayer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict

GRID_KIND_ID = "grid"

#: The markets a Grid runs on (`EPIC-039H`): the one declaration every Grid-specific caller
#: of `bot_profile_of` passes and `GridKind.supported_profiles` answers.
GRID_MARKETS: frozenset[MarketType] = SPOT_MARKETS | FUTURES_MARKETS


#: The Grid's layer of the halt-recovery policy (`EPIC-042`, `EPIC-042F`): the exchange's pause is a
#: reason only the Grid has (it is the one kind that waits for one), recovered with the common
#: budget and stalled alert and a dwell of the margin the first request waits after the pause.
GRID_RECOVERY_LAYER = RecoveryLayer(GRID_KIND_ID, changes={RATE_LIMITED: PAUSE_RULE})


class GridKind(IBotKind):
    """A ladder of resting orders across a price range."""

    def __init__(
        self,
        executor_factory: IBotExecutorFactory,
        thresholds: GridThresholds,
        backtester: IKindBacktester | None = None,
    ) -> None:
        self._executor_factory = executor_factory
        self._thresholds = thresholds
        self._backtester = backtester

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

    def backtester(self) -> IKindBacktester | None:
        return self._backtester
