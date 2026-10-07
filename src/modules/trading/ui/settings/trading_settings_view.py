from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.add_key_dialog import (
    AddKeyDialog,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from sagittarius_engine.extensions.pyside_mvc import BaseView

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLabel

    from .trading_settings_view_model import TradingSettingsViewModel

_INTRO = (
    "Add a Binance key and the app finds out which environment it belongs to: "
    "mainnet, Spot Testnet or Futures Testnet. A mainnet key goes in the "
    "operating system's keyring; a testnet key in secrets.local.json (not "
    "tracked in git). A key that can withdraw funds is refused. A key is saved "
    "when you add, replace or remove it: OK and Apply have nothing to save here."
)
_COLUMNS = ("Venue", "Key", "State")


class _RowWidgets:
    """The widgets of one venue's row, updated in place."""

    def __init__(self, venue: TradingVenue) -> None:
        self.venue = venue
        self.title = plain_label()
        self.key = plain_label()
        self.state = plain_label()
        self.state.setWordWrap(True)
        self.replace = QPushButton()
        self.replace.setObjectName(f"btnReplaceKey_{venue.name}")
        self.remove = QPushButton("Remove")
        self.remove.setObjectName(f"btnRemoveKey_{venue.name}")


class TradingSettingsView(BaseView):
    """@brief The Trading page of Tools → Options (`EPIC-033E`): one row per
    venue and the actions on a key (`BUG-176`)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: dict[TradingVenue, _RowWidgets] = {}
        self._build_ui()

    def set_view_model(self, view_model: TradingSettingsViewModel) -> None:
        self._add_key_button.clicked.connect(view_model.requestAddKey)
        self._check_button.clicked.connect(view_model.requestCheckConnections)
        view_model.rowsChanged.connect(lambda: self._apply_rows(view_model))
        view_model.busyChanged.connect(lambda: self._apply_busy(view_model))
        view_model.statusChanged.connect(lambda: self._apply_status(view_model))
        self._apply_rows(view_model)
        self._apply_busy(view_model)
        self._apply_status(view_model)

    def ask_for_key(self, hint: str) -> tuple[str, str] | None:
        """Asks for a key and a secret in a modal dialog; `None` when cancelled."""
        dialog = AddKeyDialog(hint, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.entered()

    def _apply_rows(self, view_model: TradingSettingsViewModel) -> None:
        for row in view_model.rows:
            widgets = self._rows.get(row.venue) or self._add_row(row.venue, view_model)
            widgets.title.setText(row.title)
            widgets.key.setText(row.key)
            widgets.state.setText(_worded(row.state, row.state_is_error))
            widgets.replace.setText("Replace…" if row.has_key else "Add…")
            widgets.replace.setEnabled(row.editable and not view_model.busy)
            widgets.remove.setEnabled(
                row.has_key and row.editable and not view_model.busy
            )

    def _add_row(
        self, venue: TradingVenue, view_model: TradingSettingsViewModel
    ) -> _RowWidgets:
        widgets = _RowWidgets(venue)
        grid_row = len(self._rows) + 1
        self._grid.addWidget(widgets.title, grid_row, 0)
        self._grid.addWidget(widgets.key, grid_row, 1)
        self._grid.addWidget(widgets.state, grid_row, 2)
        buttons = QHBoxLayout()
        buttons.addWidget(widgets.replace)
        buttons.addWidget(widgets.remove)
        self._grid.addLayout(buttons, grid_row, 3)
        widgets.replace.clicked.connect(
            lambda _checked=False, v=venue: view_model.requestReplaceKey(v)
        )
        widgets.remove.clicked.connect(
            lambda _checked=False, v=venue: view_model.requestRemoveKey(v)
        )
        self._rows[venue] = widgets
        return widgets

    def _apply_busy(self, view_model: TradingSettingsViewModel) -> None:
        idle = not view_model.busy
        self._busy_label.setText(view_model.busyText)
        self._add_key_button.setEnabled(idle)
        self._check_button.setEnabled(idle)
        self._apply_rows(view_model)

    def _apply_status(self, view_model: TradingSettingsViewModel) -> None:
        self._status_label.setText(
            _worded(view_model.statusMessage, view_model.statusIsError)
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        intro = plain_label(_INTRO)
        intro.setObjectName("lblTradingSettingsIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(14)
        self._grid.setVerticalSpacing(12)
        self._grid.setColumnStretch(2, 1)
        for column, heading in enumerate(_COLUMNS):
            self._grid.addWidget(plain_label(heading), 0, column)
        layout.addLayout(self._grid)

        buttons = QHBoxLayout()
        self._add_key_button = QPushButton("Add key…")
        self._add_key_button.setObjectName("btnAddKey")
        self._check_button = QPushButton("Check connections")
        self._check_button.setObjectName("btnCheckConnections")
        buttons.addWidget(self._add_key_button)
        buttons.addWidget(self._check_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._busy_label: QLabel = plain_label()
        self._busy_label.setObjectName("lblTradingSettingsBusy")
        layout.addWidget(self._busy_label)

        self._status_label = plain_label()
        self._status_label.setObjectName("lblTradingSettingsStatus")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)


def _worded(message: str, is_error: bool) -> str:
    """An error is named in words, never by weight or colour alone
    (`ui-presentation-rule.md` §1)."""
    return f"Error: {message}" if is_error and message else message
