"""`EPIC-039K` — the Spot `ReplayEngine`: the unchanged `GridReplay` and its benchmark.

@details Every figure is read from `GridReplay` and `BuyAndHold` exactly as `simulate_grid`
read them before the engine port existed; `spot_oracle` (`EPIC-039B`) pins the results byte
for byte. Spot has no funding and no liquidation, so `close_bar` has nothing to do.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.buy_and_hold import (
    BuyAndHold,
    buy_and_hold,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    PriceBar,
    PriceStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_replay import (
    GridReplay,
    ReplaySetup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.replay_engine import (
    ReplayEngine,
    ReplayOutcome,
)


class SpotReplayEngine(ReplayEngine):
    """A Spot ladder replayed by the live executor's own reactions."""

    def __init__(self, setup: ReplaySetup, first: PriceBar) -> None:
        self._replay = GridReplay(setup, first)
        self._hold: BuyAndHold = buy_and_hold(
            setup.params.capital_quote,
            first.open,
            setup.terms.taker_fee,
            setup.terms.step_size,
        )

    @property
    def plan(self) -> GridPlan:
        return self._replay.plan

    @property
    def stopped(self) -> bool:
        return self._replay.stop is not None

    def may_trade_in(self, low: Decimal, high: Decimal) -> bool:
        return self._replay.may_trade_in(low, high)

    def run_step(self, step: PriceStep) -> None:
        self._replay.run_step(step)

    def close_bar(self, bar: PriceBar, end: datetime) -> None:
        return

    def value_at(self, price: Decimal) -> Decimal:
        return self._replay.value_at(price)

    def benchmark_at(self, price: Decimal) -> Decimal:
        return self._hold.value_at(price)

    def outcome(self, last_close: Decimal) -> ReplayOutcome:
        replay = self._replay
        runtime = replay.runtime
        return ReplayOutcome(
            fills=tuple(replay.fills),
            grid_profit=runtime.realised_profit,
            unrealised=runtime.inventory * last_close - runtime.cost,
            completed_cycles=runtime.completed_cycles,
            stop_reason=replay.stop or StopReason.END_OF_DATA,
            maker_fees=replay.maker_fees,
            taker_fees=replay.taker_fees,
            final_states=replay.drawn_states(),
            average_cost=runtime.average_cost,
            stop_detail=replay.stop_detail,
        )
