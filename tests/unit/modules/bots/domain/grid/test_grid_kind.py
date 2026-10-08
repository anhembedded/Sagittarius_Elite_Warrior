"""`EPIC-029C` — Grid as an `IBotKind`: validate and overlay delegate to the planner."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderEnd,
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
    IBotExecutor,
    IBotExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_facts import IBotFacts
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import OverlayRole
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
    GridKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_overlay import (
    GridOverlaySource,
    grid_overlay,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    inputs,
)


class _Executor(IBotExecutor):
    def start(self) -> None: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def stop(self, base: BaseHandling) -> None: ...

    def confirm_resume(self) -> None: ...

    def has_resume_proposal(self) -> bool:
        return False

    @property
    def facts(self) -> IBotFacts:
        return _Facts()


class _Facts(IBotFacts):
    def on_fill(self, fill: BotOrderFill) -> None: ...

    def on_end(self, end: BotOrderEnd) -> None: ...

    def on_tick(self, price: Decimal) -> None: ...

    def on_price_age_check(self) -> None: ...

    def on_switch(self, enabled: bool, cause: TradingSwitchCause) -> None: ...

    def reconcile_after_gap(self) -> None: ...

    def halt_user_stream_down(self, down_for: timedelta) -> None: ...


class _Factory(IBotExecutorFactory):
    def create(self, bot: Bot) -> IBotExecutor:
        return _Executor()


def _kind(thresholds: GridThresholds | None = None) -> tuple[GridKind, _Factory]:
    factory = _Factory()
    return GridKind(factory, thresholds or GridThresholds()), factory


def test_the_executor_double_is_complete_and_hands_out_its_facts() -> None:
    """A double that cannot be built (a missing abstract member) hides until
    something creates one; the factory's executor must be constructible."""
    assert isinstance(_Executor().facts, IBotFacts)


def test_identity_and_factory() -> None:
    kind, factory = _kind()
    assert kind.kind_id == GRID_KIND_ID == "grid"
    assert kind.executor_factory() is factory


def test_validate_is_the_planners_verdicts() -> None:
    kind, _ = _kind()
    changed = inputs(stop_loss="percent:10")
    assert kind.validate(changed) == evaluate_grid(changed, GridThresholds()).verdicts


def test_validate_uses_the_thresholds_the_kind_was_built_with() -> None:
    strict, _ = _kind(GridThresholds(min_step_fraction=Decimal("0.5")))
    assert "STEP_BELOW_MINIMUM" in {v.code for v in strict.validate(inputs())}


def test_validate_never_raises_on_unreadable_parameters() -> None:
    kind, _ = _kind()
    assert [v.code for v in kind.validate(inputs(lower="x"))] == [
        "PARAMETERS_UNREADABLE"
    ]


def test_overlay_draws_every_level_and_both_exits_lowest_first() -> None:
    kind, _ = _kind()
    lines = kind.overlay(inputs()).lines
    roles = [line.role for line in lines]
    assert roles.count(OverlayRole.BUY_LEVEL) == 5
    assert roles.count(OverlayRole.SELL_LEVEL) == 5
    assert roles.count(OverlayRole.EMPTY_LEVEL) == 1
    assert (lines[0].role, lines[0].price) == (OverlayRole.STOP_LOSS, Decimal(57000))
    assert (lines[-1].role, lines[-1].price) == (
        OverlayRole.TAKE_PROFIT,
        Decimal(73500),
    )
    assert [line.price for line in lines] == sorted(line.price for line in lines)


def test_overlay_without_exits_or_with_bad_parameters() -> None:
    kind, _ = _kind()
    roles = {
        line.role
        for line in kind.overlay(inputs(stop_loss="off", take_profit="off")).lines
    }
    assert OverlayRole.STOP_LOSS not in roles
    assert OverlayRole.TAKE_PROFIT not in roles
    assert kind.overlay(inputs(lower="x")).lines == ()


def test_the_kinds_overlay_is_the_grid_overlay_with_the_markets_atr() -> None:
    """`EPIC-029G` — the planner preview draws the same overlay the backtest
    and the running bot draw, computed by `grid_overlay`."""
    kind, _ = _kind()
    with_atr = inputs(daily_atr=Decimal(2500))
    evaluation = evaluate_grid(with_atr, GridThresholds())
    assert evaluation.params is not None and evaluation.plan is not None

    assert kind.overlay(with_atr) == grid_overlay(
        GridOverlaySource(
            evaluation.params,
            evaluation.plan,
            GridThresholds(),
            daily_atr=Decimal(2500),
        )
    )
    assert len(kind.overlay(with_atr).bands) == 2
