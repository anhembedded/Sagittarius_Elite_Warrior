"""`EPIC-022D` — the "Thông số Chiến lược" dialog, shared by every screen
with a live strategy card (`EPIC-023C`: Trading and Dev Board both arm the
same `ArmStrategyCommand`-backed strategy, so both need the identical
parameter editor).

@details One tab, not the Backtest dialog's four. Backtest's extra tabs
carry broker properties (commission, slippage, the simulated fill model)
and a placeholder style tab; the screens this dialog serves send orders to
the real exchange, so there is no fill model to configure, and
sizing/leverage — the two things a live trader does set — live on the
strategy card itself where they are visible without opening a dialog.
Showing empty or inapplicable tabs here would be `domain-truth-rule.md`'s
"do not present an unsupported capability as available", one dialog down.

The fields themselves are `BotParamFieldWidget`, the same widget the
Backtest dialog renders, from the same `ParamGroup`/`ParamField` shape
`IStrategyCatalog.params_form()` publishes — so a strategy's parameters
look and validate identically wherever they are edited.

`EPIC-023C` moved this out of `screens/trading/` and replaced the
`DeskViewModel` type hint with `BotParamsSink` below: every screen's
ViewModel that carries the `EPIC-022D` strategy-card Signal
block satisfies it structurally, the same `ParamStepper` precedent
`param_stepper.py` already set for `BotParamFieldWidget`.

`EPIC-025` PR 4.3m: moved here from `modules/strategy/ui/strategy_params/`
— it imports only `support/ui_kit`, never a strategy, so it belongs beside
`param_field.py` rather than in the module that happens to be the source
of the data it renders. `botParamsRows: list[dict]` became
`botParamsGroups: tuple[ParamGroup, ...]`: `build_bot_params_rows`'s
QML-`Repeater` flattening is dead (PR 4.3 deleted the QML), so this dialog
now renders the strategy's declared groups directly.
"""

from __future__ import annotations

from typing import Any, Protocol

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup

from .param_field import BotParamFieldWidget
from .param_stepper import ParamStepper

_TITLE = "Strategy Parameters"
_EMPTY_TEXT = "This strategy does not declare any parameters."


class BotParamsSink(ParamStepper, Protocol):
    """@brief What this dialog reads from and writes to a screen's
    ViewModel — the `EPIC-022D` strategy-card block every implementer
    duplicates verbatim (`ParamStepper`'s own docstring explains why a
    `Protocol`, not a shared base class).

    `botParamsChanged` is a PySide6 bound `Signal`, which has no clean
    static type here — `presentation/` is excluded from the `mypy` gate
    wholesale (`pyproject.toml`, `EPIC-002A`), same as every other `Signal`
    member on a Protocol in this package.
    """

    botParamsChanged: Any
    botParamsError: str
    botParamsGroups: tuple[ParamGroup, ...]

    def requestBotParamsSave(self, values: dict) -> None: ...


class StrategyParamsDialog(QDialog):
    """@brief Edits the selected strategy's declared parameters.

    @details A stock `QDialog`: the parameters scroll once, in the middle; the
    commit buttons are a `QDialogButtonBox`, so the platform orders them
    (`ui-presentation-rule.md` §7). Save is the default button, Esc and the
    title-bar close act as Cancel, and Restore Defaults resets the fields in
    place without saving.
    """

    def __init__(
        self,
        view_model: BotParamsSink,
        parent: QWidget | None = None,
        title: str = _TITLE,
    ) -> None:
        """@param title `BOT-063` — overridable so the Dev Board's
        per-script params dialog can say "Indicator Parameters" rather
        than "Strategy Parameters" while reusing this exact class; every
        existing caller keeps the strategy wording by leaving it unset."""
        super().__init__(parent)
        self.setObjectName("strategyParamsDialog")
        self.setWindowTitle(title)
        self._vm = view_model
        self._field_widgets: list[BotParamFieldWidget] = []

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setObjectName("strategyParamsContent")

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidget(self._content)

        self._error_label = QLabel()
        self._error_label.setObjectName("lblStrategyParamsError")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults
        )
        self._restore_button = self._named_button(
            QDialogButtonBox.StandardButton.RestoreDefaults, "btnStrategyParamsRestore"
        )
        self._cancel_button = self._named_button(
            QDialogButtonBox.StandardButton.Cancel, "btnStrategyParamsCancel"
        )
        self._save_button = self._named_button(
            QDialogButtonBox.StandardButton.Save, "btnStrategyParamsSave"
        )
        self._save_button.setDefault(True)
        self._restore_button.clicked.connect(self._on_restore_clicked)
        self._buttons.accepted.connect(self._on_save_clicked)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._scroll, 1)
        layout.addWidget(self._error_label)
        layout.addWidget(self._buttons)

        self._vm.botParamsChanged.connect(self._sync_from_view_model)
        self._sync_from_view_model()

    def _named_button(self, which: QDialogButtonBox.StandardButton, name: str):
        button = self._buttons.button(which)
        button.setObjectName(name)
        return button

    @property
    def title(self) -> str:
        return self.windowTitle()

    def sizeHint(self) -> QSize:
        """Wide and tall enough for the fields as they are, never taller than
        the screen allows: the content decides, not a number written here."""
        base = super().sizeHint()
        content = self._content.sizeHint()
        scrollbar = self._scroll.verticalScrollBar().sizeHint().width()
        screen = self.screen()
        limit = (
            screen.availableGeometry().height() * 3 // 4 if screen else base.height()
        )
        chrome = base.height() - self._scroll.sizeHint().height()
        height = min(content.height() + chrome, limit)
        return QSize(max(base.width(), content.width() + scrollbar), max(height, 1))

    def _on_restore_clicked(self) -> None:
        """`BOT-063` — resets every visible field to its own declared
        default in place, without touching the ViewModel: nothing is saved
        until Save is clicked, mirroring `strategy_properties_dialog.py`'s
        own "Reset to Default" (that dialog's `reset_all_fields`)."""
        for widget in self._field_widgets:
            widget.reset_to_default()

    def collect_values(self) -> dict[str, Any]:
        """@brief What the user typed, keyed by parameter name."""
        return {
            widget.field_name: widget.value()
            for widget in self._field_widgets
            if widget.field_name
        }

    def _on_save_clicked(self) -> None:
        """@details Asks the ViewModel to save and closes only if it
        accepted. Staying open on a rejection is the point: the error
        label is inside this dialog, and closing over an invalid value
        would leave the user with a card that quietly kept the old
        parameters while they believed they had changed them."""
        self._vm.requestBotParamsSave(self.collect_values())
        if not self._vm.botParamsError:
            self.accept()

    def _sync_from_view_model(self) -> None:
        self._error_label.setText(self._vm.botParamsError)
        self._error_label.setVisible(bool(self._vm.botParamsError))
        self._rebuild_fields(self._vm.botParamsGroups)

    def _rebuild_fields(self, groups: tuple[ParamGroup, ...]) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item is None:
                # `count()` just said there is one, so this cannot happen —
                # but `takeAt()`'s own signature admits `None`, and this file
                # came under the type checker when `EPIC-025` PR 2.1e-1 moved
                # it out of `presentation/` (which mypy excludes wholesale).
                # `break` rather than `continue`: a `None` that kept the count
                # non-zero would spin this loop forever.
                break
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self._field_widgets = []

        if not groups:
            self._content_layout.addWidget(QLabel(_EMPTY_TEXT))
            self._content_layout.addStretch(1)
            return

        for group in groups:
            if group.label:
                box = QGroupBox(group.label)
                container = QVBoxLayout(box)
                self._content_layout.addWidget(box)
            else:
                container = self._content_layout
            for field in group.fields:
                field_widget = BotParamFieldWidget(field, self._vm)
                self._field_widgets.append(field_widget)
                container.addWidget(field_widget)
        self._content_layout.addStretch(1)
