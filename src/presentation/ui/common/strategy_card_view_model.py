"""The strategy card's own state, owned once (`EPIC-025` PR 2.1e, kept
shared by PR 4.3m).

@details `TradingViewModel` and `DashboardViewModel` each carried this block —
**nineteen members, name for name**: six signals, six setters the Presenter
calls, and seven `request*` slots the widgets call. Both copies were written
from the same design (`EPIC-022D` for Trading, `EPIC-023C` for the Dev Board)
and stayed identical by hand, which is how `BUG-084` and `BUG-086` each had to
be fixed twice. `tools/measure_duplicate_members.py` counted them, and
`EPIC-025`'s Phase 1 criterion ("59 duplicated members → 0") is mostly this.

@par Why here rather than `modules/strategy/ui/` (PR 2.1e's original home)
A card that picks a strategy, holds its parameters and asks to arm it is
still `strategy`'s vocabulary, not a reusable widget's — but a module's
`ui/` may not be imported by another module the instant `strategy` becomes a
real module boundary (`architecture-rule.md` §3, `EPIC-025` PR 4.4). `PR
4.3m`'s first draft answered that by deleting this class and flattening its
members directly onto `TradingViewModel`/`DashboardViewModel` — which
undid the whole point of `EPIC-025`'s Phase 1 criterion: the nineteen names
came right back as duplicates, just spelled without a `.strategy.` prefix
(`tests/unit/architecture/test_presenter_duplication_only_shrinks.py`
measured it, 32 → 63). This file is the correct fix: keep the *class* one
shared owner, move its *location* one step sideways, from a module's `ui/`
(now forbidden to cross) to `presentation/ui/common/` (never forbidden,
since both consumers are Presenters, not modules) — the same move
`strategy_arming_coordinator.py` makes in this same directory, for the
same reason.

@par The shape is the one the Backtest screen already used
`backtest/view_models/strategy_params_view_model.py` is the same idea one
screen over. The difference from that extraction is deliberate: it kept
forwarding methods on the facade so that *"no call site changes"*, and here
the call sites **do** change, to `view_model.strategy.…`. Forwarding would
have left all nineteen names defined on both screens, which is the
duplication itself rather than a way of removing it.

@par Not a widget, and not a Presenter
State plus the signals that state emits. What stays on each screen's own
view model is what belongs to *that* screen: the Enable/Disable toggle,
session stats, the symbol picker, the manual order card.
`StrategyArmingCoordinator` (this directory) is the behaviour — this is
only what it reads and writes, and its `StrategyCardViewModel` Protocol is
the port shape this class satisfies.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup
from Sagittarius_Elite_Warrior.src.support.ui_kit.param_form import (
    step_numeric_param_value,
)


class StrategyCardViewModel(QObject):
    """@brief What the strategy card shows, and what the user asked it for."""

    #: The strategy card's own state (selection, timeframe, sizing, leverage,
    #: and what is armed). One signal for the whole block because the card
    #: redraws as a unit.
    strategyConfigChanged = Signal()
    #: The parameter groups behind the "Thông số Chiến lược" dialog.
    #: Separate from `strategyConfigChanged` because rebuilding a form the
    #: user is typing into is not the same event as the card's own state
    #: changing.
    botParamsChanged = Signal()
    #: The most recent `SignalGeneratedEvent`.
    lastSignalChanged = Signal()

    #: "Nạp chiến lược". Deliberately NOT emitted when the user merely picks
    #: a different strategy in the combo: picking and arming are two actions,
    #: and conflating them is how a bot arms itself while the user is still
    #: choosing.
    armRequested = Signal()
    #: "Gỡ chiến lược".
    disarmRequested = Signal()
    #: The parameters dialog's Save.
    #: The `type: ignore[arg-type]`s in this file are one thing: Qt takes
    #: a type *name* as a string at runtime (`"QVariantMap"`, `"QVariantList"`,
    #: `"QStringList"`) while the PySide6 stub declares `type`. That is the
    #: same false-positive class `pyproject.toml`'s wholesale `presentation/`
    #: exclusion exists for (`EPIC-002A` §2).
    botParamsSaveRequested = Signal("QVariantMap")  # type: ignore[arg-type]

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._strategy_options: list[dict] = []
        self._interval_options: list[str] = []
        self._selected_strategy_key = ""
        self._live_interval = ""
        self._sizing_percent = 0.0
        self._leverage = 1.0
        self._armed_summary = ""
        self._strategy_busy = False
        self._bot_params_groups: tuple[ParamGroup, ...] = ()
        self._bot_params_error = ""
        self._last_signal_text = ""

    # ------------------------------------------------------------------ #
    # Strategy card
    # ------------------------------------------------------------------ #

    @Property("QVariantList", notify=strategyConfigChanged)  # type: ignore[arg-type]
    def strategyOptions(self) -> list[dict]:
        """`[{"key": ..., "label": ...}]` — `IStrategyCatalog.options()`,
        already humanised for display but always carrying the key the
        port needs."""
        return self._strategy_options

    @Property("QStringList", notify=strategyConfigChanged)  # type: ignore[arg-type]
    def intervalOptions(self) -> list[str]:
        return self._interval_options

    @Property(str, notify=strategyConfigChanged)
    def selectedStrategyKey(self) -> str:
        return self._selected_strategy_key

    @Property(str, notify=strategyConfigChanged)
    def liveInterval(self) -> str:
        return self._live_interval

    @Property(float, notify=strategyConfigChanged)
    def sizingPercent(self) -> float:
        return self._sizing_percent

    @Property(float, notify=strategyConfigChanged)
    def leverage(self) -> float:
        return self._leverage

    @Property(str, notify=strategyConfigChanged)
    def armedSummary(self) -> str:
        """What is actually armed right now, in words — empty when
        nothing is. Never a restatement of the combo's current selection:
        the whole point of the "Nạp chiến lược" button is that choosing
        and running are two different things, and this line is the only
        place the user can see which one they are looking at."""
        return self._armed_summary

    @Property(bool, notify=strategyConfigChanged)
    def strategyBusy(self) -> bool:
        return self._strategy_busy

    @Slot(list, list)
    def set_strategy_options(
        self, strategy_options: list[dict], interval_options: list[str]
    ) -> None:
        self._strategy_options = list(strategy_options)
        self._interval_options = list(interval_options)
        self.strategyConfigChanged.emit()

    @Slot(str, str, float, float)
    def set_strategy_selection(
        self,
        strategy_key: str,
        interval: str,
        sizing_percent: float,
        leverage: float,
    ) -> None:
        self._selected_strategy_key = strategy_key
        self._live_interval = interval
        self._sizing_percent = sizing_percent
        self._leverage = leverage
        self.strategyConfigChanged.emit()

    @Slot(str, bool)
    def set_armed_summary(self, summary: str, busy: bool) -> None:
        self._armed_summary = summary
        self._strategy_busy = busy
        self.strategyConfigChanged.emit()

    @Slot(str)
    def requestStrategySelection(self, strategy_key: str) -> None:
        """Records the pick. Arming is a separate, explicit action."""
        if strategy_key and strategy_key != self._selected_strategy_key:
            self._selected_strategy_key = strategy_key
            self.strategyConfigChanged.emit()

    @Slot(str)
    def requestIntervalSelection(self, interval: str) -> None:
        if interval and interval != self._live_interval:
            self._live_interval = interval
            self.strategyConfigChanged.emit()

    @Slot(float)
    def requestSizingPercent(self, percent: float) -> None:
        self._sizing_percent = percent

    @Slot(float)
    def requestLeverage(self, leverage: float) -> None:
        self._leverage = leverage

    @Slot()
    def requestArm(self) -> None:
        self.armRequested.emit()

    @Slot()
    def requestDisarm(self) -> None:
        self.disarmRequested.emit()

    # ------------------------------------------------------------------ #
    # "Thông số Chiến lược"
    # ------------------------------------------------------------------ #

    @Property("QVariantList", notify=botParamsChanged)  # type: ignore[arg-type]
    def botParamsGroups(self) -> tuple[ParamGroup, ...]:
        return self._bot_params_groups

    @Property(str, notify=botParamsChanged)
    def botParamsError(self) -> str:
        return self._bot_params_error

    def set_bot_params(self, groups: tuple[ParamGroup, ...]) -> None:
        self._bot_params_groups = groups
        self.botParamsChanged.emit()

    def step_bot_param_value(
        self, field_name: str, raw_value: str, direction: int
    ) -> str:
        """`ParamStepper` — normalises one Up/Down/wheel step against the
        current groups, so `BotParamFieldWidget` never does the clamping
        arithmetic itself."""
        for group in self._bot_params_groups:
            for field in group.fields:
                if field.name == field_name:
                    return step_numeric_param_value(field, raw_value, direction)
        return raw_value

    @Slot(str)
    def set_bot_params_error(self, message: str) -> None:
        self._bot_params_error = message
        self.botParamsChanged.emit()

    @Slot("QVariantMap")
    def requestBotParamsSave(self, values: dict) -> None:
        self.botParamsSaveRequested.emit(values)

    # ------------------------------------------------------------------ #
    # Last signal
    # ------------------------------------------------------------------ #

    @Property(str, notify=lastSignalChanged)
    def lastSignalText(self) -> str:
        return self._last_signal_text

    @Slot(str)
    def set_last_signal_text(self, text: str) -> None:
        self._last_signal_text = text
        self.lastSignalChanged.emit()
