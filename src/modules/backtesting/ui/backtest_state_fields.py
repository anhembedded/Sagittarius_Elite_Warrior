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

from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.currency import (
    Currency,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestExecutionMode,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.time_range_preset import (
    TimeRangePreset,
)

#: Free-text fields are `QLineEdit` contents the user is mid-way through
#: typing as often as not, so they are validated for shape rather than
#: meaning — the ViewModel's own setters already parse them (see
#: `orderSizeText`, which updates `orderSizeValue` as a side effect). A
#: generous ceiling that still rejects a corrupted blob is the point.
_MAX_TEXT_LENGTH = 64

#: Longest symbol any exchange lists is well under this; a generous ceiling
#: that still rejects a corrupted blob is the point, not a precise limit.
_MAX_SYMBOL_LENGTH = 20


@dataclass(frozen=True, slots=True)
class StateField:
    """One remembered value: where it lives on the ViewModel, and what makes
    a stored copy of it worth applying."""

    key: str
    prop: str
    """Where the value lives, relative to the ViewModel.

    May be a dotted path (`EPIC-003F6`): `"broker_sim.commissionText"` once
    that group has moved off the facade, `"selectedCurrency"` while it has
    not. Both halves go through `read_prop()`/`write_prop()`, so a row can
    be flipped the moment its group migrates and no earlier."""
    is_valid: Callable[[Any, Any], bool]
    """`(value, view_model) -> bool`. Takes the ViewModel too because some
    fields are only valid against a list it owns at runtime (the strategy
    keys actually registered, the timezones actually supported)."""


def read_prop(view_model: Any, path: str) -> Any:
    """`getattr` along a dotted path.

    @details `EPIC-003F6` moves state off `BackTestViewModel` onto six
    sub-ViewModels, so `"commissionText"` becomes
    `"broker_sim.commissionText"`. Walking the path here is what keeps that
    a one-line edit per row instead of a special case at every call site.

    Deliberately **not** defensive: a bad path is a typo in the table above,
    and an `AttributeError` naming it is far more useful than a `None` that
    quietly captures an empty form and restores it over the user's real one.
    """
    for segment in path.split("."):
        view_model = getattr(view_model, segment)
    return view_model


def write_prop(view_model: Any, path: str, value: Any) -> None:
    """`setattr` at the end of a dotted path — the inverse of `read_prop`."""
    *parents, attribute = path.split(".")
    for segment in parents:
        view_model = getattr(view_model, segment)
    setattr(view_model, attribute, value)


def read_notifier(view_model: Any, path: str) -> Any:
    """The `<prop>Changed` signal for a (possibly dotted) `path`.

    @details Qt names a property's notifier `<prop>Changed`, and
    `signal_wiring.connect_state_tracking()` derives every row's notifier
    that way. With a dotted path the suffix belongs on the **last** segment:
    `"broker_sim.commissionText"` notifies via
    `view_model.broker_sim.commissionTextChanged`, not via a non-existent
    `view_model.<"broker_sim.commissionTextChanged">`.

    Returns `None` when the signal is absent, so the caller can raise with
    the field key in the message rather than an opaque `AttributeError`.
    """
    *parents, attribute = path.split(".")
    for segment in parents:
        view_model = getattr(view_model, segment, None)
        if view_model is None:
            return None
    return getattr(view_model, f"{attribute}Changed", None)


def _text(value: Any, _view_model: Any) -> bool:
    return isinstance(value, str) and len(value) <= _MAX_TEXT_LENGTH


def _symbol_shape(value: Any, _view_model: Any) -> bool:
    """A plausible exchange symbol: alphanumeric, non-empty, short."""
    return (
        isinstance(value, str)
        and value.strip().isalnum()
        and len(value.strip()) <= _MAX_SYMBOL_LENGTH
    )


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
        try:
            options = read_prop(view_model, options_prop) or []
        except AttributeError:
            # An options list that is not there yet is not a reason to throw
            # away a remembered value's validation — it is a reason to reject
            # the value, which is what an empty list already does.
            options = []
        if entry_key is None:
            return value in options
        return any(
            isinstance(option, dict) and option.get(entry_key) == value
            for option in options
        )

    return check


#: `symbol` and `timeframe` were held back from `EPIC-010F` until `EPIC-010H`
#: settled the three-tier order — they are the only two values in the app where
#: `user_config`'s `DEFAULT_*` keys and a remembered value both claim the same
#: field. That order is now
#:
#:     ui_state  >  user_config DEFAULT_*  >  module constants
#:
#: and `SettingsPresenter._discard_outranked_state()` honours its mandatory
#: consequence: saving those defaults drops exactly these two remembered keys,
#: so changing Settings visibly takes effect instead of losing to an older
#: value.
BACKTEST_STATE_FIELDS: tuple[StateField, ...] = (
    StateField(
        # Shape, not membership — unlike `strategy` above. `symbolOptions` is
        # filled by `SymbolOptionsCoordinator` on the thread pool (`EPIC-019A`),
        # so at restore time it is still empty and a membership check would
        # reject every symbol, every launch. Same conclusion as `EPIC-010D`
        # reached for the Dev Board, by a different route.
        "symbol",
        "selectedSymbol",
        _symbol_shape,
    ),
    StateField("timeframe", "selectedTimeframe", _among("timeframeOptions")),
    StateField(
        # `strategyOptions` entries are `{"key": ..., "name": ...}` dicts
        # (`backtest_presenter.py:471`), not plain strings — comparing a
        # key against the raw list would silently never match.
        "strategy",
        "strategy_params.selectedStrategyKey",
        _among("strategy_params.strategyOptions", "key"),
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
        "broker_sim.orderSizeType",
        _one_of(kind.value for kind in PositionSizingType),
    ),
    StateField("order_size", "broker_sim.orderSizeText", _text),
    StateField("pyramiding", "broker_sim.pyramiding", _whole(1, 1000)),
    StateField(
        "commission_type",
        "broker_sim.commissionType",
        _one_of(kind.value for kind in CommissionType),
    ),
    StateField("commission", "broker_sim.commissionText", _text),
    StateField("slippage_ticks", "broker_sim.slippageTicks", _whole(0, 10_000)),
    StateField("long_leverage", "broker_sim.longLeverage", _number(0, 1000)),
    StateField("short_leverage", "broker_sim.shortLeverage", _number(0, 1000)),
    StateField("take_profit_enabled", "broker_sim.takeProfitPctEnabled", _flag),
    StateField("take_profit_pct", "broker_sim.takeProfitPctText", _text),
    StateField(
        "time_range_preset",
        "time_range.preset",
        _one_of(preset.value for preset in TimeRangePreset),
    ),
    StateField("custom_start", "time_range.customStartText", _text),
    StateField("custom_end", "time_range.customEndText", _text),
    StateField(
        # Timezone options key their id as `"id"`, while the time-range preset
        # options above use `"value"` — two different shapes for the same kind
        # of list, which is why each row names its own key rather than the
        # table assuming one convention.
        "timezone",
        "time_range.displayTimezone",
        _among("time_range.displayTimezoneOptions", "id"),
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
