"""The strategy card's own state, owned once (`EPIC-025` PR 2.1e).

@details `TradingViewModel` and `DashboardViewModel` each carried this block —
**nineteen members, name for name**: six signals, six setters the Presenter
calls, and seven `request*` slots the widgets call. Both copies were written
from the same design (`EPIC-022D` for Trading, `EPIC-023C` for the Dev Board)
and stayed identical by hand, which is how `BUG-084` and `BUG-086` each had to
be fixed twice. `tools/measure_duplicate_members.py` counted them, and
`EPIC-025`'s Phase 1 criterion ("59 duplicated members → 0") is mostly this.

@par Why here rather than in `support/ui_kit`
A card that picks a strategy, holds its parameters and asks to arm it is
`strategy`'s vocabulary, not a reusable widget's. HLD §6.1 forbids a support
package from knowing a module exists, and this class names `LiveStrategyConfig`'s
own bounds through the widgets that bind to it. It is the module's `ui/`, which
is exactly what ADR D22 and HLD §4 mean by a bounded context owning its own
display code.

@par The shape is the one the Backtest screen already used
`backtest/view_models/strategy_params_view_model.py` is the same idea one screen
over — *"whoever eventually shares a single strategy-params ViewModel between the
two screens needs both halves to look like each other first"*, its own docstring
says. They did look like each other; this is that sharing. The difference from
that extraction is deliberate: it kept forwarding methods on the facade so that
*"no call site changes"*, and here the call sites **do** change, to
`view_model.strategy.…`. Forwarding would have left all nineteen names defined
on both screens, which is the duplication itself rather than a way of removing
it.

@par Not a widget, and not a Presenter
State plus the signals that state emits, exactly like the Backtest half. What
stays on each screen's own view model is what belongs to *that* screen: the
Enable/Disable toggle, session stats, the symbol picker, the manual order card.
`StrategyArmingCoordinator` is the behaviour — this is only what it reads and
writes, and its `_StrategyCardView` Protocol is the port shape one of these
satisfies.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.modules.strategy.ui.strategy_params import (
    step_numeric_param_value,
)


class StrategyCardViewModel(QObject):
    """@brief What the strategy card shows, and what the user asked it for."""

    #: The strategy card's own state (selection, timeframe, sizing, leverage,
    #: and what is armed). One signal for the whole block because the card
    #: redraws as a unit.
    strategyConfigChanged = Signal()
    #: The parameter rows behind the "Thông số Chiến lược" dialog. Separate
    #: from `strategyConfigChanged` because rebuilding a form the user is
    #: typing into is not the same event as the card's own state changing.
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
    #: The four `type: ignore[arg-type]`s in this file are one thing: Qt takes
    #: a type *name* as a string at runtime (`"QVariantMap"`, `"QVariantList"`,
    #: `"QStringList"`) while the PySide6 stub declares `type`. That is the
    #: same false-positive class `pyproject.toml`'s wholesale `presentation/`
    #: exclusion exists for (`EPIC-002A` §2), and this block came out of that
    #: excluded tree — so it is re-keyed debt, not new. Taken as four local
    #: ignores rather than a path exclusion, which is `qt_platform.py`'s
    #: precedent from PR 1.6f: the file stays checked for everything else, and
    #: it earned that immediately — two real errors (`union-attr` in the params
    #: dialog, an optional enum index in the arming coordinator) surfaced the
    #: moment this package left `presentation/`, and both are fixed rather
    #: than excluded.
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
        self._bot_params_schema: list[dict] = []
        self._bot_params_rows: list[dict] = []
        self._bot_params_error = ""
        self._last_signal_text = ""

    # ------------------------------------------------------------------ #
    # Strategy card
    # ------------------------------------------------------------------ #

    @Property("QVariantList", notify=strategyConfigChanged)  # type: ignore[arg-type]
    def strategyOptions(self) -> list[dict]:
        """`[{"key": ..., "label": ...}]` — the registry's keys, humanised
        for display but always carrying the key the command needs."""
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
    def botParamsRows(self) -> list[dict]:
        return self._bot_params_rows

    @Property(str, notify=botParamsChanged)
    def botParamsError(self) -> str:
        return self._bot_params_error

    @Slot(list, list)
    def set_bot_params(self, schema: list[dict], rows: list[dict]) -> None:
        """@details Schema and rows are set together because they are two
        views of one thing: rows are what the dialog renders, schema is
        what `step_bot_param_value()` clamps against. Letting them be set
        separately is how they end up describing different strategies."""
        self._bot_params_schema = list(schema)
        self._bot_params_rows = list(rows)
        self.botParamsChanged.emit()

    def step_bot_param_value(
        self, field_name: str, raw_value: str, direction: int
    ) -> str:
        """`ParamStepper` — normalises one Up/Down/wheel step against the
        current schema, so `BotParamFieldWidget` never does the clamping
        arithmetic itself."""
        for group in self._bot_params_schema:
            for field in group.get("fields", []):
                if field.get("name") == field_name:
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
