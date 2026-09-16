"""`EPIC-003E2` — turning the Backtest toolbar into a `BacktestRunConfig`.

@details `logic/` holds stateless transforms (`code-rule.md` §3), and this
is the biggest one the Presenter still carried: `_build_run_config` was 107
lines, `_get_current_config` 36, together ~7% of a 1.966-line file, and
neither touched Presenter state beyond three values that are passed in
here explicitly.

@par No side effects, on purpose
The original wrote its failures straight out — `view_model.set_result(...)`
and `_log_dev_trace(...)` interleaved with the parsing. That is what made
it untestable without a Presenter. Here the function **returns** what
happened (`RunConfigOutcome`: the config or an error message, plus the dev
traces in order) and the Presenter performs the two side effects in the
same order it always did. A pure builder can be asserted on directly; the
Presenter keeps owning what the user sees.

@par Two builders, not one, because they answer different questions
- `build_run_config()` is the **strict** one: it runs
  `PreBacktestAssertionPipeline` and refuses (`config is None`) rather than
  guess. It is what actually starts a run.
- `snapshot_current_config()` is the **lenient** one: never fails, falls
  back (`10000.0`, `Currency.USD`, `timeframe_or_fallback`) and is used
  only for the dirty-tracking summary label. Its `broker_config` is
  deliberately the untouched `BrokerSimulationConfig()` default — see
  `BackTestPresenter._fee_rate_percent_for_last_run`, which exists
  precisely because this snapshot must NOT be read for real fee rates.

Merging the two would mean either a run starting on guessed values or a
label that cannot be rendered while the form is half-filled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.domain.value_objects.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.currency import Currency
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_fsm_matrix import (
    BacktestRunConfig,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_state import (
    BacktestExecutionMode,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.pre_backtest_assertions import (
    PreBacktestAssertionPipeline,
    PreBacktestInput,
    parse_custom_datetime,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.time_range_preset import (
    TimeRangePreset,
    resolve_time_range,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.timeframe_parsing import (
    timeframe_or_fallback,
)

#: Shown when the strategy picker is empty — a run cannot be guessed into
#: existence, so this is a refusal, not a default.
NO_STRATEGY_MESSAGE = "No strategy has been registered yet."

#: A kline can be closed locally yet still be absent from the exchange's
#: historical endpoint for a short publication window. Live-ended backtests
#: therefore stop one full bar behind `now`; this is a deterministic data
#: watermark, not a claim that the chart has no newer in-progress candle.
LIVE_BACKTEST_END_DELAY_INTERVALS = 1

#: `snapshot_current_config()`'s fallback when the capital field cannot be
#: parsed. Only ever reaches a summary label, never a run.
FALLBACK_INITIAL_BALANCE = 10000.0


class StrategyInputs(Protocol):
    """What the builders read off `BackTestViewModel.strategy_params`."""

    @property
    def selectedStrategyKey(self) -> str: ...


class TimeRangeInputs(Protocol):
    """…off `BackTestViewModel.time_range`."""

    @property
    def preset(self) -> str: ...
    @property
    def customStartText(self) -> str: ...
    @property
    def customEndText(self) -> str: ...


class BrokerSimInputs(Protocol):
    """…off `BackTestViewModel.broker_sim`."""

    @property
    def orderSizeType(self) -> str: ...
    @property
    def orderSizeValue(self) -> float: ...
    @property
    def pyramiding(self) -> int: ...
    @property
    def slippageTicks(self) -> int: ...
    @property
    def commissionType(self) -> str: ...
    @property
    def commissionValue(self) -> float: ...
    @property
    def longLeverage(self) -> float: ...
    @property
    def shortLeverage(self) -> float: ...
    @property
    def takeProfitPctEnabled(self) -> bool: ...
    @property
    def takeProfitPctText(self) -> str: ...


class RunConfigInputs(Protocol):
    """What the builders read off the ViewModel — nothing else.

    An explicit contract rather than `BackTestViewModel` itself
    (`architecture-rule.md`: explicit contracts, no implicit duck-typing):
    it is what lets a test hand in a plain object, and it is the list of
    fields a ViewModel split must keep reachable.

    `EPIC-003F6` reshaped it to match the object graph rather than the old
    flat facade: three of these fields now come from sub-ViewModels, so the
    Protocol says so. Written flat, the contract would have kept claiming a
    flat ViewModel exists long after it stopped.
    """

    @property
    def selectedTimeframe(self) -> str: ...
    @property
    def selectedCurrency(self) -> str: ...
    @property
    def initialCapitalText(self) -> str: ...
    @property
    def strategy_params(self) -> StrategyInputs: ...
    @property
    def time_range(self) -> TimeRangeInputs: ...
    @property
    def broker_sim(self) -> BrokerSimInputs: ...


@dataclass(frozen=True)
class DevTrace:
    """One `_log_dev_trace` call the Presenter still has to make."""

    event: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunConfigOutcome:
    """Either a config, or the message explaining why there is none.

    Never both, and never neither: `error_message` is non-empty exactly
    when `config is None`. `traces` is emitted in order regardless — the
    dev trace of a rejected config is the most useful one there is.
    """

    config: BacktestRunConfig | None
    error_message: str = ""
    traces: tuple[DevTrace, ...] = ()

    @property
    def is_valid(self) -> bool:
        return self.config is not None


def published_candle_cutoff(now: datetime, timeframe: TimeFrame) -> datetime:
    """The latest live boundary safe for historical backtesting."""
    delay_seconds = timeframe.to_seconds() * LIVE_BACKTEST_END_DELAY_INTERVALS
    return now - timedelta(seconds=delay_seconds)


def build_run_config(
    view_model: RunConfigInputs,
    *,
    symbol: str,
    strategy_params: dict[str, Any],
    execution_mode: BacktestExecutionMode,
    now: datetime | None = None,
) -> RunConfigOutcome:
    """Read and validate the toolbar; refuse rather than guess.

    @param now Injectable clock so a test can assert the published-candle
    watermark instead of racing the wall clock. Defaults to `datetime.now(UTC)`.
    """
    preset = TimeRangePreset(view_model.time_range.preset)

    # `BUG-109` — resolved BEFORE the assertions below, not after: a preset
    # like "365 ngày qua" is just as wide as a hand-typed custom range for
    # `TickModeRequiresBoundedRangeRule`'s purposes, and it needs the real
    # (start_time, end_time) pair to check that, not the raw preset/text
    # `is_unbounded_range`/`is_custom_range` alone could see. A malformed
    # custom date here still resolves to `None` (via `parse_custom_datetime`)
    # rather than raising — `CustomDateRangeRule` below is what actually
    # rejects that shape, this block only needs a value or `None`.
    custom_start: datetime | None = None
    custom_end: datetime | None = None
    if preset is TimeRangePreset.CUSTOM:
        custom_start = parse_custom_datetime(view_model.time_range.customStartText)
        custom_end = parse_custom_datetime(view_model.time_range.customEndText)

    range_now = now or datetime.now(UTC)
    if preset is not TimeRangePreset.CUSTOM:
        range_now = published_candle_cutoff(
            range_now, TimeFrame(view_model.selectedTimeframe)
        )
    start_time, end_time = resolve_time_range(
        preset, range_now, custom_start, custom_end
    )

    assertions = PreBacktestAssertionPipeline.default().validate(
        PreBacktestInput(
            capital_text=view_model.initialCapitalText,
            is_custom_range=preset is TimeRangePreset.CUSTOM,
            custom_start_text=view_model.time_range.customStartText,
            custom_end_text=view_model.time_range.customEndText,
            is_unbounded_range=preset is TimeRangePreset.ALL_HISTORY,
            is_tick_mode=execution_mode is BacktestExecutionMode.HISTORICAL_TICK,
            start_time=start_time,
            end_time=end_time,
        )
    )
    if assertions:
        issue = assertions[0]
        return RunConfigOutcome(
            config=None,
            error_message=issue.message,
            traces=(
                DevTrace(
                    "run_config_invalid",
                    {
                        "reason": issue.field.value,
                        "capital": view_model.initialCapitalText,
                    },
                ),
            ),
        )

    initial_balance = float(view_model.initialCapitalText)

    if not view_model.strategy_params.selectedStrategyKey:
        return RunConfigOutcome(
            config=None,
            error_message=NO_STRATEGY_MESSAGE,
            traces=(DevTrace("run_config_invalid", {"reason": "missing_strategy"}),),
        )

    config = BacktestRunConfig(
        strategy_key=view_model.strategy_params.selectedStrategyKey,
        timeframe=TimeFrame(view_model.selectedTimeframe),
        initial_balance=initial_balance,
        start_time=start_time,
        end_time=end_time,
        strategy_params=strategy_params,
        currency=Currency(view_model.selectedCurrency),
        symbol=symbol,
        execution_mode=execution_mode,
        position_sizing=_position_sizing(view_model.broker_sim),
        broker_config=_broker_config(view_model.broker_sim),
    )
    return RunConfigOutcome(
        config=config,
        traces=(
            DevTrace(
                "run_config_built",
                {
                    "symbol": symbol,
                    "strategy": view_model.strategy_params.selectedStrategyKey,
                    "timeframe": view_model.selectedTimeframe,
                    "start": start_time,
                    "end": end_time,
                    "has_params": bool(strategy_params),
                },
            ),
        ),
    )


def snapshot_current_config(
    view_model: RunConfigInputs,
    *,
    symbol: str,
    strategy_params: dict[str, Any],
    execution_mode: BacktestExecutionMode,
    now: datetime | None = None,
) -> BacktestRunConfig:
    """The lenient variant: always returns something, for the dirty-tracking
    summary label only. See this module's docstring for why it must not be
    read for fee rates."""
    timeframe = timeframe_or_fallback(view_model.selectedTimeframe)

    try:
        balance = float(view_model.initialCapitalText)
    except (ValueError, TypeError):
        balance = FALLBACK_INITIAL_BALANCE

    try:
        currency = Currency(view_model.selectedCurrency)
    except ValueError:
        currency = Currency.USD

    preset = view_model.time_range.preset
    if preset == TimeRangePreset.CUSTOM.value:
        start_dt = parse_custom_datetime(view_model.time_range.customStartText)
        end_dt = parse_custom_datetime(view_model.time_range.customEndText)
    else:
        try:
            start_dt, end_dt = resolve_time_range(
                TimeRangePreset(preset), now or datetime.now(UTC)
            )
        except ValueError:
            start_dt, end_dt = None, None

    return BacktestRunConfig(
        strategy_key=view_model.strategy_params.selectedStrategyKey,
        timeframe=timeframe,
        initial_balance=balance,
        start_time=start_dt,
        end_time=end_dt,
        strategy_params=strategy_params,
        currency=currency,
        symbol=symbol,
        execution_mode=execution_mode,
    )


def _position_sizing(broker: BrokerSimInputs) -> PositionSizing:
    """An unknown sizing type falls back to the app's default rather than
    raising: the value came from a persisted state file, and a screen that
    refuses to open is worse than one that opens on the default."""
    try:
        sizing_type = PositionSizingType(broker.orderSizeType)
    except ValueError:
        sizing_type = PositionSizingType.PERCENT_OF_EQUITY
    return PositionSizing(type=sizing_type, value=broker.orderSizeValue)


def _broker_config(broker: BrokerSimInputs) -> BrokerSimulationConfig:
    try:
        commission_type = CommissionType(broker.commissionType)
    except ValueError:
        commission_type = CommissionType.PERCENT

    #: Off unless the user both ticked the box AND typed a positive number:
    #: a take-profit of 0% would close every position at entry.
    take_profit_pct: float | None = None
    if broker.takeProfitPctEnabled:
        try:
            parsed = float(broker.takeProfitPctText)
        except ValueError:
            parsed = 0.0
        if parsed > 0:
            take_profit_pct = parsed

    return BrokerSimulationConfig(
        pyramiding=broker.pyramiding,
        slippage_ticks=broker.slippageTicks,
        commission_type=commission_type,
        commission_value=broker.commissionValue,
        long_leverage=broker.longLeverage,
        short_leverage=broker.shortLeverage,
        take_profit_pct=take_profit_pct,
    )
