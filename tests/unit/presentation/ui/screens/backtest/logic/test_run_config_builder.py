"""`EPIC-003E2` — `logic/run_config_builder.py`.

These assertions used to be impossible to write: the same logic lived
inside `BackTestPresenter._build_run_config`, wrote its failures straight
to a ViewModel, and needed a whole Presenter (thread manager, dispatcher,
FSM, view) to reach. The builder is a pure function, so the fixture below
is a plain object with attributes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.domain.value_objects.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.currency import Currency
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_fsm_matrix import (
    BacktestExecutionMode,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.run_config_builder import (
    FALLBACK_INITIAL_BALANCE,
    NO_STRATEGY_MESSAGE,
    build_run_config,
    published_candle_cutoff,
    snapshot_current_config,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.time_range_preset import (
    TimeRangePreset,
)

FIXED_NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


@dataclass
class FakeStrategy:
    selectedStrategyKey: str = "ema_crossover"


@dataclass
class FakeTimeRange:
    preset: str = TimeRangePreset.LAST_30_DAYS.value
    customStartText: str = ""
    customEndText: str = ""


@dataclass
class FakeBroker:
    orderSizeType: str = PositionSizingType.PERCENT_OF_EQUITY.value
    orderSizeValue: float = 100.0
    pyramiding: int = 1
    slippageTicks: int = 0
    commissionType: str = CommissionType.PERCENT.value
    commissionValue: float = 0.1
    longLeverage: float = 1.0
    shortLeverage: float = 1.0
    takeProfitPctEnabled: bool = False
    takeProfitPctText: str = "2.0"


@dataclass
class FakeInputs:
    """Every field `RunConfigInputs` declares, with a runnable default.

    The names are `mixedCase` because they are Qt property names on the
    real ViewModel — renaming them here would make this double stop
    matching the contract it stands in for, so `N815` is silenced for the
    block rather than the names changed.

    Nested since `EPIC-003F6`, mirroring `BackTestViewModel`'s real shape:
    the three sub-objects are the sub-ViewModels the builder reads through
    now that the flat facade is going away.
    """

    # ruff: noqa: N815
    selectedTimeframe: str = TimeFrame.ONE_HOUR.value
    selectedCurrency: str = Currency.USD.value
    initialCapitalText: str = "10000"
    strategy_params: FakeStrategy = field(default_factory=FakeStrategy)
    time_range: FakeTimeRange = field(default_factory=FakeTimeRange)
    broker_sim: FakeBroker = field(default_factory=FakeBroker)


def _build(inputs: FakeInputs, **overrides):
    return build_run_config(
        inputs,
        symbol=overrides.pop("symbol", "BTCUSDT"),
        strategy_params=overrides.pop("strategy_params", {"fast": 9}),
        execution_mode=overrides.pop("execution_mode", BacktestExecutionMode.BAR_CLOSE),
        now=overrides.pop("now", FIXED_NOW),
    )


# --------------------------------------------------------------------- #
# The strict builder
# --------------------------------------------------------------------- #


def test_a_valid_toolbar_produces_a_config_and_one_trace() -> None:
    outcome = _build(FakeInputs())

    assert outcome.is_valid
    assert outcome.error_message == ""
    assert [t.event for t in outcome.traces] == ["run_config_built"]
    config = outcome.config
    assert config.strategy_key == "ema_crossover"
    assert config.symbol == "BTCUSDT"
    assert config.timeframe is TimeFrame.ONE_HOUR
    assert config.initial_balance == 10000.0
    assert config.strategy_params == {"fast": 9}


def test_an_empty_strategy_is_refused_rather_than_defaulted() -> None:
    """There is no sensible strategy to guess; running the wrong one is
    worse than not running."""
    outcome = _build(FakeInputs(strategy_params=FakeStrategy(selectedStrategyKey="")))

    assert outcome.config is None
    assert outcome.error_message == NO_STRATEGY_MESSAGE
    assert [t.event for t in outcome.traces] == ["run_config_invalid"]


@pytest.mark.parametrize("capital", ["", "abc", "0", "-5"])
def test_an_unusable_capital_is_refused_with_a_message_and_a_trace(
    capital: str,
) -> None:
    outcome = _build(FakeInputs(initialCapitalText=capital))

    assert outcome.config is None
    assert outcome.error_message != ""
    assert outcome.traces[0].event == "run_config_invalid"
    assert outcome.traces[0].fields["capital"] == capital


def test_a_rejected_config_still_reports_why_in_its_trace() -> None:
    """The dev trace of a refusal is the most useful one there is — a
    builder that only returned `None` would leave the log silent about
    which field was wrong."""
    outcome = _build(FakeInputs(initialCapitalText="abc"))

    assert outcome.traces[0].fields["reason"] != ""


def test_a_custom_range_uses_the_typed_boundaries_verbatim() -> None:
    outcome = _build(
        FakeInputs(
            time_range=FakeTimeRange(
                preset=TimeRangePreset.CUSTOM.value,
                customStartText="2026-01-01 00:00",
                customEndText="2026-02-01 00:00",
            )
        )
    )

    assert outcome.is_valid
    assert outcome.config.start_time == datetime(2026, 1, 1, tzinfo=UTC)
    assert outcome.config.end_time == datetime(2026, 2, 1, tzinfo=UTC)


def test_a_preset_range_stops_one_full_bar_behind_now() -> None:
    """The publication watermark: the most recent closed candle may not be
    on the exchange's historical endpoint yet, so a preset run must not ask
    for it. Asserted against an injected clock rather than the wall clock."""
    outcome = _build(FakeInputs(selectedTimeframe=TimeFrame.ONE_HOUR.value))

    assert outcome.config.end_time == published_candle_cutoff(
        FIXED_NOW, TimeFrame.ONE_HOUR
    )


def test_take_profit_is_off_unless_both_ticked_and_positive() -> None:
    """A take-profit of 0% would close every position at entry."""
    off = _build(
        FakeInputs(
            broker_sim=FakeBroker(takeProfitPctEnabled=False, takeProfitPctText="5")
        )
    )
    zero = _build(
        FakeInputs(
            broker_sim=FakeBroker(takeProfitPctEnabled=True, takeProfitPctText="0")
        )
    )
    junk = _build(
        FakeInputs(
            broker_sim=FakeBroker(takeProfitPctEnabled=True, takeProfitPctText="abc")
        )
    )
    on = _build(
        FakeInputs(
            broker_sim=FakeBroker(takeProfitPctEnabled=True, takeProfitPctText="5")
        )
    )

    assert off.config.broker_config.take_profit_pct is None
    assert zero.config.broker_config.take_profit_pct is None
    assert junk.config.broker_config.take_profit_pct is None
    assert on.config.broker_config.take_profit_pct == 5.0


def test_an_unknown_sizing_or_commission_type_falls_back_to_the_default() -> None:
    """These values come from a persisted state file. A screen that
    refuses to open is worse than one that opens on the app default."""
    outcome = _build(
        FakeInputs(
            broker_sim=FakeBroker(
                orderSizeType="no_such_mode", commissionType="no_such_type"
            )
        )
    )

    assert outcome.config.position_sizing.type is PositionSizingType.PERCENT_OF_EQUITY
    assert outcome.config.broker_config.commission_type is CommissionType.PERCENT


def test_the_broker_numbers_reach_the_config_unchanged() -> None:
    """The clamping is `BrokerSimViewModel`'s job (`EPIC-003F4`); the
    builder must not quietly apply a second, different opinion."""
    outcome = _build(
        FakeInputs(
            broker_sim=FakeBroker(
                pyramiding=3, slippageTicks=2, longLeverage=5.0, shortLeverage=7.0
            )
        )
    )

    broker = outcome.config.broker_config
    assert (broker.pyramiding, broker.slippage_ticks) == (3, 2)
    assert (broker.long_leverage, broker.short_leverage) == (5.0, 7.0)


def test_the_365_day_preset_in_tick_mode_is_refused_not_dispatched() -> None:
    """`BUG-109` — the actual reported hang: picking the standard "365 ngày
    qua" preset while in Realtime/tick mode used to sail straight through
    to an `IRangeCoverage` probe at the tick interval with no
    progress bar and no cancellation. `is_unbounded_range` alone never
    caught it (`start_time` is a real datetime, not `None`) — this proves
    the fix reaches all the way from the toolbar preset to a refusal, not
    just the isolated rule in `test_pre_backtest_assertions.py`."""
    outcome = _build(
        FakeInputs(
            time_range=FakeTimeRange(preset=TimeRangePreset.LAST_365_DAYS.value)
        ),
        execution_mode=BacktestExecutionMode.HISTORICAL_TICK,
    )

    assert outcome.config is None
    assert "7 days" in outcome.error_message


def test_the_7_day_preset_in_tick_mode_still_runs() -> None:
    """Pins the boundary the fix must not overshoot — BOT-075's own
    validated feasible window stays usable."""
    outcome = _build(
        FakeInputs(time_range=FakeTimeRange(preset=TimeRangePreset.LAST_7_DAYS.value)),
        execution_mode=BacktestExecutionMode.HISTORICAL_TICK,
    )

    assert outcome.is_valid


def test_the_365_day_preset_outside_tick_mode_still_runs() -> None:
    """`BAR_CLOSE` mode never hits the tick-interval coverage query, so the
    same wide preset stays fine there — same scoping `BUG-073` pinned for
    the unbounded case."""
    outcome = _build(
        FakeInputs(
            time_range=FakeTimeRange(preset=TimeRangePreset.LAST_365_DAYS.value)
        ),
        execution_mode=BacktestExecutionMode.BAR_CLOSE,
    )

    assert outcome.is_valid


# --------------------------------------------------------------------- #
# The lenient snapshot
# --------------------------------------------------------------------- #


def _snapshot(inputs: FakeInputs):
    return snapshot_current_config(
        inputs,
        symbol="BTCUSDT",
        strategy_params={},
        execution_mode=BacktestExecutionMode.BAR_CLOSE,
        now=FIXED_NOW,
    )


def test_the_snapshot_never_fails_on_a_half_filled_form() -> None:
    """It backs a label that has to render while the user is still
    typing — refusing would blank the dirty-tracking line."""
    config = _snapshot(
        FakeInputs(initialCapitalText="", selectedCurrency="not_a_currency")
    )

    assert config.initial_balance == FALLBACK_INITIAL_BALANCE
    assert config.currency is Currency.USD


def test_the_snapshot_leaves_the_broker_config_at_its_default() -> None:
    """`BackTestPresenter._fee_rate_percent_for_last_run` exists precisely
    because this snapshot must NOT be read for the fee actually applied —
    pinning that here so the two never quietly converge."""
    config = _snapshot(
        FakeInputs(broker_sim=FakeBroker(commissionValue=0.5, longLeverage=9.0))
    )

    assert config.broker_config.commission_value != 0.5
    assert config.broker_config.long_leverage != 9.0


def test_an_unparseable_custom_range_becomes_no_range_not_an_error() -> None:
    config = _snapshot(
        FakeInputs(
            time_range=FakeTimeRange(
                preset=TimeRangePreset.CUSTOM.value,
                customStartText="yesterday",
                customEndText="",
            )
        )
    )

    assert config.start_time is None
    assert config.end_time is None
