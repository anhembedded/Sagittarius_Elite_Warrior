"""Pure, extensible local assertions for a Backtest run request (BOT-095E)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Protocol

from Sagittarius_Elite_Warrior.src.presentation.ui.constants import DATETIME_FORMAT

_INVALID_CAPITAL_TEMPLATE = "Invalid initial capital: {value!r}"
_NON_POSITIVE_CAPITAL_MESSAGE = "Initial capital must be greater than 0."
_INVALID_CUSTOM_START_MESSAGE = f"Invalid start date — format {DATETIME_FORMAT}."
_INVALID_CUSTOM_END_MESSAGE = f"Invalid end date — format {DATETIME_FORMAT}."
_INVALID_CUSTOM_RANGE_MESSAGE = "Start date must be before end date."
_TICK_MODE_REQUIRES_BOUNDED_RANGE_MESSAGE = (
    'Realtime mode (tick-based) does not support "All History" — please '
    "choose a bounded time range. Checking data coverage at tick (second) "
    "resolution with no start point makes verification slower with every "
    "retry and it never catches up."
)
#: `BUG-109` — `Tasks/reports/tick_data_feasibility.md` §3.2/§3.3 measured
#: a single 7-day/1s coverage probe (query + handler) at ~17s and concluded
#: it is "not usable synchronously — MUST run in background + progress +
#: cancel". `_coverage_is_ready()` (`execution_coordinator.py`) calls this
#: exact query type synchronously on a background thread with NO progress
#: reporting of its own — a real session picked the standard "365 ngày qua"
#: preset in tick mode (a *bounded* range, so the old unbounded-only check
#: never caught it) and the app appeared to hang with nothing on screen for
#: minutes. `RangeCoverageService` has no cancellation
#: token either (`BUG-073`'s own finding) — the only reliable mitigation is
#: refusing to dispatch the hazardous shape at all, same approach `BUG-073`
#: already established for the unbounded case.
_MAX_TICK_MODE_RANGE_DAYS = 7
_TICK_MODE_RANGE_TOO_WIDE_MESSAGE = (
    "Realtime mode (tick-based) supports at most "
    f"{_MAX_TICK_MODE_RANGE_DAYS} days per run — the selected range is too "
    "wide. Checking data at tick (second) resolution over a wide range "
    "will freeze the UI for minutes with no progress bar."
)


class BacktestInputField(str, Enum):
    """Stable UI targets for local pre-run validation messages."""

    INITIAL_CAPITAL = "initialCapital"
    CUSTOM_START = "customStart"
    CUSTOM_END = "customEnd"
    TIME_RANGE_PRESET = "timeRangePreset"


@dataclass(frozen=True)
class PreBacktestInput:
    """Raw, user-editable Backtest fields that can be validated locally."""

    capital_text: str
    is_custom_range: bool
    custom_start_text: str
    custom_end_text: str
    #: BOT-076 — True only for the ALL_HISTORY preset (start_time=None).
    #: Named around the trait that actually matters (no lower bound), not
    #: the preset enum, so this stays meaningful if another unbounded
    #: preset is ever added.
    is_unbounded_range: bool = False
    #: BOT-076 — True when execution_mode is HISTORICAL_TICK. A plain bool
    #: rather than importing BacktestExecutionMode, so this module stays
    #: decoupled from the FSM layer the way its other fields already are.
    is_tick_mode: bool = False
    #: BUG-109 — the *resolved* range (post `resolve_time_range()`), not raw
    #: preset/text: a preset like "365 ngày qua" is just as wide as a
    #: hand-typed custom range, and both need the same width check. `None`
    #: for either means "unknown/still resolving" — `TickModeRequiresBoundedRangeRule`
    #: only checks width when both are present, so an unresolved transient
    #: state (same one `is_unbounded_range` alone used to miss) never false-rejects.
    start_time: datetime | None = None
    end_time: datetime | None = None


@dataclass(frozen=True)
class BacktestInputIssue:
    """One observable validation failure, tied to the owning UI field."""

    field: BacktestInputField
    message: str


class PreBacktestAssertionRule(Protocol):
    """One independently extensible local Backtest input rule."""

    def validate(self, input_: PreBacktestInput) -> BacktestInputIssue | None:
        """Return an issue only when this rule is violated."""


class InitialCapitalRule:
    """Reject capital values that PaperExchange cannot simulate honestly."""

    def validate(self, input_: PreBacktestInput) -> BacktestInputIssue | None:
        try:
            capital = float(input_.capital_text)
        except (TypeError, ValueError):
            return BacktestInputIssue(
                BacktestInputField.INITIAL_CAPITAL,
                _INVALID_CAPITAL_TEMPLATE.format(value=input_.capital_text),
            )
        if not math.isfinite(capital):
            return BacktestInputIssue(
                BacktestInputField.INITIAL_CAPITAL,
                _INVALID_CAPITAL_TEMPLATE.format(value=input_.capital_text),
            )
        if capital <= 0:
            return BacktestInputIssue(
                BacktestInputField.INITIAL_CAPITAL,
                _NON_POSITIVE_CAPITAL_MESSAGE,
            )
        return None


class CustomDateRangeRule:
    """Validate only a selected custom range; preset ranges need no parsing."""

    def validate(self, input_: PreBacktestInput) -> BacktestInputIssue | None:
        if not input_.is_custom_range:
            return None

        start = _parse_custom_datetime(input_.custom_start_text)
        if start is None:
            return BacktestInputIssue(
                BacktestInputField.CUSTOM_START,
                _INVALID_CUSTOM_START_MESSAGE,
            )

        if not input_.custom_end_text.strip():
            return None

        end = _parse_custom_datetime(input_.custom_end_text)
        if end is None:
            return BacktestInputIssue(
                BacktestInputField.CUSTOM_END,
                _INVALID_CUSTOM_END_MESSAGE,
            )
        if start >= end:
            return BacktestInputIssue(
                BacktestInputField.CUSTOM_END,
                _INVALID_CUSTOM_RANGE_MESSAGE,
            )
        return None


def tick_mode_range_too_wide(
    is_tick_mode: bool, start_time: datetime | None, end_time: datetime | None
) -> bool:
    """`BUG-109` — True when `is_tick_mode` and the resolved `(start_time,
    end_time)` span exceeds `_MAX_TICK_MODE_RANGE_DAYS`. A plain function
    (not only `TickModeRequiresBoundedRangeRule.validate()`) so
    `ChartPreviewCoordinator` — which already has resolved datetimes from
    `BacktestRunConfig`, not the raw preset/text `PreBacktestInput` reads —
    can reuse the exact same threshold instead of re-deriving it under a
    different number. Deliberately does NOT treat `start_time is None`
    (unbounded) as "too wide" here — that is `is_unbounded_range`'s own,
    differently-worded hazard in `TickModeRequiresBoundedRangeRule`; a
    caller with only resolved datetimes (no `BacktestRunConfig` preset)
    should still bounded-check ALL_HISTORY (`start_time is None`) itself
    where it already does, unchanged since `BUG-073`."""
    if not is_tick_mode or start_time is None or end_time is None:
        return False
    return (end_time - start_time).days > _MAX_TICK_MODE_RANGE_DAYS


class TickModeRequiresBoundedRangeRule:
    """Reject Realtime/tick mode combined with an unbounded start_time, OR
    (`BUG-109`) a *bounded* range wider than `_MAX_TICK_MODE_RANGE_DAYS`.

    A None start_time makes `IRangeCoverage`'s SQL scan every
    row ever synced for that symbol/interval with no lower bound (see
    sqlalchemy_repository.py's window-function coverage query). At 1-second
    granularity that scan gets slower every time more tick data is synced,
    while the live-trailing end_time cutoff keeps advancing with real time
    regardless — a real session got stuck retrying "Đồng bộ dữ liệu ngay"
    forever because the coverage round-trip could never finish faster than
    the cutoff kept moving. BOT-075's own validated feasibility number was a
    bounded 7-day window, never unbounded history.

    A *bounded* range does not dodge the same query cost: `BUG-109` reproduced
    the identical hang via the plain "365 ngày qua" preset — start_time is a
    real datetime, not None, so the check above alone never caught it. Both
    hazards get the same treatment: refuse to dispatch rather than attempt a
    query with no cancellation and no progress reporting.
    """

    def validate(self, input_: PreBacktestInput) -> BacktestInputIssue | None:
        if not input_.is_tick_mode:
            return None
        if input_.is_unbounded_range:
            return BacktestInputIssue(
                BacktestInputField.TIME_RANGE_PRESET,
                _TICK_MODE_REQUIRES_BOUNDED_RANGE_MESSAGE,
            )
        if tick_mode_range_too_wide(
            input_.is_tick_mode, input_.start_time, input_.end_time
        ):
            return BacktestInputIssue(
                BacktestInputField.TIME_RANGE_PRESET,
                _TICK_MODE_RANGE_TOO_WIDE_MESSAGE,
            )
        return None


@dataclass(frozen=True)
class PreBacktestAssertionPipeline:
    """Runs local rules without assuming exchange metadata or an order intent."""

    rules: tuple[PreBacktestAssertionRule, ...]

    @classmethod
    def default(cls) -> PreBacktestAssertionPipeline:
        """The rules that can be truthfully evaluated from local UI input."""

        return cls(
            (
                InitialCapitalRule(),
                CustomDateRangeRule(),
                TickModeRequiresBoundedRangeRule(),
            )
        )

    def validate(self, input_: PreBacktestInput) -> tuple[BacktestInputIssue, ...]:
        issues: list[BacktestInputIssue] = []
        for rule in self.rules:
            issue = rule.validate(input_)
            if issue is not None:
                issues.append(issue)
        return tuple(issues)


def parse_custom_datetime(raw: str) -> datetime | None:
    """Convert one UI range boundary to the UTC instant Backtest uses."""

    return _parse_custom_datetime(raw)


def _parse_custom_datetime(raw: str) -> datetime | None:
    try:
        return datetime.strptime(raw.strip(), DATETIME_FORMAT).replace(tzinfo=UTC)
    except (AttributeError, ValueError):
        return None
