"""Pure, extensible local assertions for a Backtest run request (BOT-095E)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Protocol

_CUSTOM_TIME_FORMAT = "%Y-%m-%d %H:%M"
_INVALID_CAPITAL_TEMPLATE = "Vốn ban đầu không hợp lệ: {value!r}"
_NON_POSITIVE_CAPITAL_MESSAGE = "Vốn ban đầu phải lớn hơn 0."
_INVALID_CUSTOM_START_MESSAGE = (
    f"Ngày bắt đầu không hợp lệ — định dạng {_CUSTOM_TIME_FORMAT}."
)
_INVALID_CUSTOM_END_MESSAGE = (
    f"Ngày kết thúc không hợp lệ — định dạng {_CUSTOM_TIME_FORMAT}."
)
_INVALID_CUSTOM_RANGE_MESSAGE = "Ngày bắt đầu phải trước ngày kết thúc."


class BacktestInputField(str, Enum):
    """Stable UI targets for local pre-run validation messages."""

    INITIAL_CAPITAL = "initialCapital"
    CUSTOM_START = "customStart"
    CUSTOM_END = "customEnd"


@dataclass(frozen=True)
class PreBacktestInput:
    """Raw, user-editable Backtest fields that can be validated locally."""

    capital_text: str
    is_custom_range: bool
    custom_start_text: str
    custom_end_text: str


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


@dataclass(frozen=True)
class PreBacktestAssertionPipeline:
    """Runs local rules without assuming exchange metadata or an order intent."""

    rules: tuple[PreBacktestAssertionRule, ...]

    @classmethod
    def default(cls) -> PreBacktestAssertionPipeline:
        """The rules that can be truthfully evaluated from local UI input."""

        return cls((InitialCapitalRule(), CustomDateRangeRule()))

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
        return datetime.strptime(raw.strip(), _CUSTOM_TIME_FORMAT).replace(tzinfo=UTC)
    except (AttributeError, ValueError):
        return None
