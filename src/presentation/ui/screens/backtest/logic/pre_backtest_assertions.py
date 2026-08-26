"""Pure, extensible local assertions for a Backtest run request (BOT-095E)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Protocol

from Sagittarius_Elite_Warrior.src.presentation.ui.constants import DATETIME_FORMAT

_INVALID_CAPITAL_TEMPLATE = "Vốn ban đầu không hợp lệ: {value!r}"
_NON_POSITIVE_CAPITAL_MESSAGE = "Vốn ban đầu phải lớn hơn 0."
_INVALID_CUSTOM_START_MESSAGE = (
    f"Ngày bắt đầu không hợp lệ — định dạng {DATETIME_FORMAT}."
)
_INVALID_CUSTOM_END_MESSAGE = (
    f"Ngày kết thúc không hợp lệ — định dạng {DATETIME_FORMAT}."
)
_INVALID_CUSTOM_RANGE_MESSAGE = "Ngày bắt đầu phải trước ngày kết thúc."
_TICK_MODE_REQUIRES_BOUNDED_RANGE_MESSAGE = (
    'Chế độ Realtime (theo tick) không hỗ trợ "Toàn bộ lịch sử" — hãy chọn '
    "một khoảng thời gian có giới hạn. Kiểm tra phạm vi dữ liệu ở độ phân "
    "giải tick (giây) không có điểm bắt đầu khiến việc xác minh dữ liệu "
    "chậm dần theo mỗi lần thử và không bao giờ bắt kịp."
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


class TickModeRequiresBoundedRangeRule:
    """Reject Realtime/tick mode combined with an unbounded start_time.

    A None start_time makes GetBacktestRangeCoverageQuery's SQL scan every
    row ever synced for that symbol/interval with no lower bound (see
    sqlalchemy_repository.py's window-function coverage query). At 1-second
    granularity that scan gets slower every time more tick data is synced,
    while the live-trailing end_time cutoff keeps advancing with real time
    regardless — a real session got stuck retrying "Đồng bộ dữ liệu ngay"
    forever because the coverage round-trip could never finish faster than
    the cutoff kept moving. BOT-075's own validated feasibility number was a
    bounded 7-day window, never unbounded history.
    """

    def validate(self, input_: PreBacktestInput) -> BacktestInputIssue | None:
        if input_.is_tick_mode and input_.is_unbounded_range:
            return BacktestInputIssue(
                BacktestInputField.TIME_RANGE_PRESET,
                _TICK_MODE_REQUIRES_BOUNDED_RANGE_MESSAGE,
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
