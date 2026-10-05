"""Backtest strategy parameters: the strategy's inputs and the simulated
broker's properties, in two tabs (BOT-104).

`EPIC-033L` makes it a stock `QDialog` titled after its command, Strategy
Parameters, with Save, Cancel and Restore Defaults in a `QDialogButtonBox`.
The Properties tab is `BrokerPropertiesTab`. The two "Coming soon" tabs,
Style and Visibility, are gone: a tab holding only a promise is a page to
open and find nothing on.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit.binding import BindingGroup
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit.widget_value import (
    connect_value_committed,
    read_widget_value,
    write_widget_value,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.param_form import (
    BotParamFieldWidget,
)

from ..logic.broker_properties_schema import BROKER_PROPERTY_FIELDS, owner_of
from .broker_properties_tab import BrokerPropertiesTab

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

#: Names the command that opens it: the Run setup's Strategy parameters….
_TITLE = "Strategy Parameters"
_NO_INPUTS_TEXT = "This strategy has no input parameters to configure."


#: What Restore Defaults restores each broker property to, keyed by the same
#: `BrokerPropertyField.key` everything else uses (BUG-064). A table rather
#: than twelve `setText`/`setValue`/`setChecked` calls, so a new property gets
#: its default declared in the one place the rest of it is already declared —
#: and so Reset can never drift from the widget list the way it silently could
#: when it named every widget by hand.
_BROKER_PROPERTY_DEFAULTS: dict[str, Any] = {
    "initial_capital": "10000",
    "currency": "USD",
    "order_size_type": "percent_of_equity",
    "order_size_text": "100",
    "pyramiding": 1,
    "commission_type": "percent",
    "commission_text": "0.1",
    "slippage_ticks": 0,
    "long_leverage": 1,
    "short_leverage": 1,
    "take_profit_enabled": False,
    "take_profit_pct_text": "2.0",
}


def _field_names(groups: Sequence[ParamGroup]) -> list[str]:
    """The declared field names in `botParamsGroups`, in order — the part of
    the schema that decides whether the Inputs tab's widgets must be
    rebuilt (BUG-064). Values are deliberately not part of this."""
    return [field.name for group in groups for field in group.fields]


class StrategyPropertiesDialog(QDialog):
    """@brief The run's strategy inputs and broker properties."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("botParamsDialog")
        self.setWindowTitle(_TITLE)
        self._vm = view_model
        self._strategy_name = ""
        self._field_widgets: list[BotParamFieldWidget] = []

        self._inputs_tab = QWidget()
        self._inputs_layout = QVBoxLayout(self._inputs_tab)
        self._inputs_layout.setObjectName("strategyInputsContent")
        self._properties_tab = BrokerPropertiesTab()
        self._property_widgets = self._properties_tab.widgets
        self._bindings = self._bind_broker_properties()
        self._vm.broker_sim.marketChanged.connect(self._show_leverage_for_market)
        self._show_leverage_for_market()

        self._tabs = QTabWidget()
        self._tabs.addTab(_scrolled(self._inputs_tab), "&Inputs")
        self._tabs.addTab(_scrolled(self._properties_tab), "P&roperties")
        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs, 1)
        layout.addWidget(self._build_buttons())

        view_model.strategy_params.botParamsGroupsChanged.connect(self._sync_inputs)
        view_model.botParamsSaved.connect(self.accept)

    def _bind_broker_properties(self) -> BindingGroup:
        """Declares each Properties-tab widget and its ViewModel property to
        BE the same value, in both directions (BUG-064).

        This is the QML binding this dialog was ported away from, rebuilt on
        QtWidgets: `text: vm.broker_sim.orderSizeText` became one `bind(...)` row. What
        it replaces is not just shorter code but a whole category of "did
        somebody remember to sync?" — there is no longer a `_sync_properties()`
        to call at the right moment, and no payload to collect at the right
        moment, because neither direction waits for a moment any more.

        The ViewModel is the single source of truth from here on: the widgets
        follow it, including when it changes from outside this dialog.
        """
        bindings = BindingGroup()
        for field in BROKER_PROPERTY_FIELDS:
            bindings.bind(
                self._property_widgets[field.key],
                owner_of(self._vm, field),
                field.vm_attribute,
                field.coerce,
            )
        # Not a value, so not a binding: the % field is only editable while the
        # box is on (the tab connects the two), seeded once for the state the
        # ViewModel is already in.
        self._properties_tab.take_profit_pct.setEnabled(
            bool(self._vm.broker_sim.takeProfitPctEnabled)
        )
        return bindings

    def _build_buttons(self) -> QDialogButtonBox:
        standard = QDialogButtonBox.StandardButton
        buttons = QDialogButtonBox(
            standard.Save | standard.Cancel | standard.RestoreDefaults
        )
        named = {
            standard.Save: "btnBotParamsSave",
            standard.Cancel: "btnBotParamsCancel",
            standard.RestoreDefaults: "btnResetBotParams",
        }
        for which, object_name in named.items():
            button = buttons.button(which)
            button.setObjectName(object_name)
            button.setAutoDefault(False)
        self._buttons = buttons
        # BUG-064 — was "Lưu & Chạy lại" ("Save & Re-run"). Saving no longer
        # starts a backtest; the platform's Save says what it does.
        buttons.button(standard.Save).clicked.connect(self.save_and_close)
        buttons.button(standard.RestoreDefaults).clicked.connect(self.reset_all_fields)
        buttons.rejected.connect(self.reject)
        return buttons

    def showEvent(self, event) -> None:
        """BUG-064 — a button that answers Enter once wiped every setting.
        Here Enter means "commit this field" (editingFinished), so no button
        may answer it; and a button box makes its first accept button the
        default as it is shown, so the default is taken back after."""
        super().showEvent(event)
        for button in self._buttons.buttons():
            if isinstance(button, QPushButton):
                button.setDefault(False)

    def open_for_strategy(self, strategy_name: str) -> None:
        self._strategy_name = strategy_name
        self.setWindowTitle(f"{_TITLE}: {strategy_name}" if strategy_name else _TITLE)
        self._sync_inputs()
        # No `_sync_properties()` any more: the Properties tab is bound to the
        # ViewModel (BUG-064), so it is already showing current values —
        # whether or not anyone thought to refresh it before opening.
        self.open()

    def _sync_inputs(self) -> None:
        """Rebuilds the Inputs tab's widgets from the current schema.

        Skips the rebuild entirely when the schema still describes the SAME
        set of fields (BUG-064). Reason: committing an edit refreshes the
        schema so the stored values are current, which fires
        `botParamsGroupsChanged` — and blindly rebuilding there would
        `deleteLater()` the very widget the user is typing in, mid-edit,
        every time they tab to the next field. Only the field *set* matters
        for whether widgets must be recreated; values are already correct in
        the live widgets (the user typed them), so a values-only change has
        nothing to rebuild. Switching strategies does change the field set,
        and still rebuilds.
        """
        groups = self._vm.strategy_params.botParamsGroups
        if self._field_widgets and _field_names(groups) == [
            fw.field_name for fw in self._field_widgets
        ]:
            return

        while self._inputs_layout.count():
            item = self._inputs_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._field_widgets = []

        if not groups:
            self._inputs_layout.addWidget(QLabel(_NO_INPUTS_TEXT))
            return

        for group in groups:
            # A group's title is the strategy author's text, never an access
            # key: a group box would read "Entry & exit" as Alt+E.
            box = QGroupBox(group.label.replace("&", "&&"))
            rows = QVBoxLayout(box)
            for field in group.fields:
                field_widget = BotParamFieldWidget(field, self._vm.strategy_params)
                rows.addWidget(field_widget)
                self._field_widgets.append(field_widget)
            self._inputs_layout.addWidget(box)
        self._inputs_layout.addStretch(1)
        self._wire_commit_on_edit(fw.input_widget for fw in self._field_widgets)

    def reset_all_fields(self) -> None:
        """Writes the declared defaults into the widgets. The Properties tab's
        bindings carry each one straight through to the ViewModel — Reset does
        not need its own path to storage (BUG-064)."""
        for field_widget in self._field_widgets:
            field_widget.reset_to_default()
        for key, value in _BROKER_PROPERTY_DEFAULTS.items():
            write_widget_value(self._property_widgets[key], value)

    def _wire_commit_on_edit(self, widgets: Iterable[QWidget]) -> None:
        """Auto-commit for the Inputs tab, which is NOT bound (BUG-064).

        Strategy parameters cannot simply be bound the way broker properties
        are: they go through `parse_bot_params()`, which must be able to
        *reject* a value (out of a declared min/max) and show an inline error
        rather than store it. A binding has no reject step — it makes two
        things equal — so these keep the validate-then-store payload path.

        `connect_value_committed()` (kit) still picks the right signal from
        Qt's own metadata, so every input kind is covered, not just text
        boxes.
        """
        for widget in widgets:
            connect_value_committed(widget, self._commit_edited_values)

    def _collect_payload(self) -> dict:
        """The values the presenter's save/commit handlers expect.

        `properties` is read from the widgets rather than the ViewModel purely
        so the payload shape stays what the coordinator already validates
        against; the bindings mean those two agree by construction, since a
        widget edit has already reached the ViewModel by the time this runs.
        """
        return {
            "inputs": {fw.field_name: fw.value() for fw in self._field_widgets},
            "properties": {
                key: read_widget_value(widget)
                for key, widget in self._property_widgets.items()
            },
        }

    def _show_leverage_for_market(self) -> None:
        """EPIC-027D — Spot trades at 1× only (ADR D3): no leverage to set."""
        spot = self._vm.broker_sim.market == MarketType.SPOT.value
        self._properties_tab.leverage_section.setVisible(not spot)

    def _commit_edited_values(self) -> None:
        """Persist what is currently typed, and nothing more — the
        focus-loss/Enter path.

        BUG-064's two wrong versions both reused the save pipeline (one closed
        the dialog on every tab, the other dispatched `RUN_REQUESTED` and
        started a backtest). The commit path is its own signal end to end
        (`requestStrategyPropertiesCommit` -> `strategyPropertiesCommitRequested`
        -> `StrategyConfigCoordinator.commit_strategy_properties`): it
        validates and stores the values and stops there.
        """
        self._vm.requestStrategyPropertiesCommit(self._collect_payload())

    def save_and_close(self) -> None:
        """The Save button: persist and close the dialog (the close happens
        via `botParamsSaved` -> `accept`, so an invalid value leaves it open
        with the inline error showing).

        BUG-064 — this used to also start a backtest, which is why it was
        named `save_and_rerun` and labelled "Lưu & Chạy lại". Running is the
        user's decision, made with the Run button; the config change alone
        just marks any existing results stale.
        """
        self._vm.requestStrategyPropertiesSave(self._collect_payload())


def _scrolled(content: QWidget) -> QScrollArea:
    """A tab scrolls once, at the tab (`ui-presentation-rule.md` §3)."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(content)
    return scroll
