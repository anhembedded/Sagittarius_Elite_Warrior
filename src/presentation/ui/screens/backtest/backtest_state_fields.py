"""`EPIC-010F` — which Backtest form values are remembered, and what counts
as a valid one.

@par Why a table instead of nineteen `if isinstance(...)` blocks
`010D` and `010E` validate three values and two values respectively, so a
hand-written block per field reads fine there. This screen has nineteen. Written
the same way it would be nineteen near-identical blocks in `capture_state()` and
nineteen more in `restore_state()`, where a single field silently missing from
one of the two halves is invisible in review — exactly the kind of drift the
key-constant convention in `010D` exists to prevent, at four times the size.

So the fields are declared once, and both halves iterate the same declaration.
Adding a value means adding one row. It cannot then be captured but not
restored, or vice versa.

@par This is still per-field validation, not a blanket type check
D5 says a restored value is a request: each row carries its own predicate, and
`restore_state()` applies the rows independently, so one corrupt value falls
back on its own without taking the other eighteen with it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.value_objects.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.currency import Currency
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_fsm_matrix import (
    BacktestExecutionMode,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.time_range_preset import (
    TimeRangePreset,
)

#: Free-text fields are `QLineEdit` contents the user is mid-way through
#: typing as often as not, so they are validated for shape rather than
#: meaning — the ViewModel's own setters already parse them (see
#: `orderSizeText`, which updates `orderSizeValue` as a side effect). A
#: generous ceiling that still rejects a corrupted blob is the point.
_MAX_TEXT_LENGTH = 64


@dataclass(frozen=True, slots=True)
class StateField:
    """One remembered value: where it lives on the ViewModel, and what makes
    a stored copy of it worth applying."""

    key: str
    prop: str
    is_valid: Callable[[Any, Any], bool]
    """`(value, view_model) -> bool`. Takes the ViewModel too because some
    fields are only valid against a list it owns at runtime (the strategy
    keys actually registered, the timezones actually supported)."""


def _text(value: Any, _view_model: Any) -> bool:
    return isinstance(value, str) and len(value) <= _MAX_TEXT_LENGTH


def _flag(value: Any, _view_model: Any) -> bool:
    return isinstance(value, bool)


def _whole(low: int, high: int) -> Callable[[Any, Any], bool]:
    def check(value: Any, _view_model: Any) -> bool:
        # `isinstance(True, int)` is True in Python, so booleans are excluded
        # explicitly — `{"pyramiding": true}` in a hand-edited file would
        # otherwise be applied as 1.
        return (
            isinstance(value, int)
            and not isinstance(value, bool)
            and low <= value <= high
        )

    return check


def _number(low: float, high: float) -> Callable[[Any, Any], bool]:
    def check(value: Any, _view_model: Any) -> bool:
        return (
            isinstance(value, int | float)
            and not isinstance(value, bool)
            and low <= value <= high
        )

    return check


def _one_of(allowed: Iterable[str]) -> Callable[[Any, Any], bool]:
    """A closed set known at import time — an enum's own members."""
    members = frozenset(allowed)

    def check(value: Any, _view_model: Any) -> bool:
        return isinstance(value, str) and value in members

    return check


def _among(
    options_prop: str, entry_key: str | None = None
) -> Callable[[Any, Any], bool]:
    """A list the ViewModel only knows at runtime.

    @details `strategyOptions` depends on what the registry actually holds and
    `displayTimezoneOptions` on the platform, so neither can be frozen into a
    constant here. `entry_key` picks the field out of option lists whose
    entries are `{"value": ..., "label": ...}` dicts rather than plain strings.
    """

    def check(value: Any, view_model: Any) -> bool:
        if not isinstance(value, str):
            return False
        options = getattr(view_model, options_prop, None) or []
        if entry_key is None:
            return value in options
        return any(
            isinstance(option, dict) and option.get(entry_key) == value
            for option in options
        )

    return check


#: Deliberately absent: `selectedSymbol` and `selectedTimeframe`. They are the
#: only two values in the app where `user_config`'s `DEFAULT_*` keys and a
#: remembered value would both claim the same field, and settling that needs
#: `EPIC-010H` — see this task's file for the full reasoning.
BACKTEST_STATE_FIELDS: tuple[StateField, ...] = (
    StateField(
        # `strategyOptions` entries are `{"key": ..., "name": ...}` dicts
        # (`backtest_presenter.py:471`), not plain strings — comparing a
        # key against the raw list would silently never match.
        "strategy",
        "selectedStrategyKey",
        _among("strategyOptions", "key"),
    ),
    StateField("capital", "initialCapitalText", _text),
    StateField("currency", "selectedCurrency", _one_of(Currency.list_values())),
    StateField(
        "execution_mode",
        "executionMode",
        _one_of(mode.value for mode in BacktestExecutionMode),
    ),
    StateField(
        "order_size_type",
        "orderSizeType",
        _one_of(kind.value for kind in PositionSizingType),
    ),
    StateField("order_size", "orderSizeText", _text),
    StateField("pyramiding", "pyramiding", _whole(1, 1000)),
    StateField(
        "commission_type",
        "commissionType",
        _one_of(kind.value for kind in CommissionType),
    ),
    StateField("commission", "commissionText", _text),
    StateField("slippage_ticks", "slippageTicks", _whole(0, 10_000)),
    StateField("long_leverage", "longLeverage", _number(0, 1000)),
    StateField("short_leverage", "shortLeverage", _number(0, 1000)),
    StateField("take_profit_enabled", "takeProfitPctEnabled", _flag),
    StateField("take_profit_pct", "takeProfitPctText", _text),
    StateField(
        "time_range_preset",
        "timeRangePreset",
        _one_of(preset.value for preset in TimeRangePreset),
    ),
    StateField("custom_start", "customStartText", _text),
    StateField("custom_end", "customEndText", _text),
    StateField(
        # Timezone options key their id as `"id"`, while the time-range preset
        # options above use `"value"` — two different shapes for the same kind
        # of list, which is why each row names its own key rather than the
        # table assuming one convention.
        "timezone",
        "displayTimezone",
        _among("displayTimezoneOptions", "id"),
    ),
    StateField("extended_metrics", "showExtendedMetrics", _flag),
)


# --- EPIC-010G — the indicator-script checklist ----------------------------
#: Kept out of `BACKTEST_STATE_FIELDS` on purpose: the checklist is a
#: `QAbstractListModel`, not a ViewModel property, so it has no `prop` to
#: `getattr` and no `<prop>Changed` notifier of the shape the table assumes.
#: Forcing it into a row would mean special-casing the row everywhere the
#: table is iterated, which is worse than two named constants beside it.
SCRIPTS_ENABLED_KEY = "scripts_enabled"
SCRIPTS_TOUCHED_KEY = "scripts_touched"


def is_key_list(value: object) -> bool:
    """A remembered list of script keys.

    @details Shape only — whether a key still names a registered script is
    `IndicatorScriptListModel.restore_selection()`'s job, which intersects
    against the rows that actually exist.
    """
    return isinstance(value, list) and all(isinstance(item, str) for item in value)
