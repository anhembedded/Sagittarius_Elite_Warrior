from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.add_key_dialog import (
    AddKeyDialog,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.connection_state_words import (
    StateKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.public_address_words import (
    ADVICE,
    CAPTION,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.content_width_scroll_area import (
    ContentWidthScrollArea,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.state_badge import StateBadge
from Sagittarius_Elite_Warrior.src.support.ui_kit.state_look import StateLook
from sagittarius_engine.extensions.pyside_mvc import BaseView

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLabel

    from .trading_settings_view_model import (
        KeyRow,
        TradingSettingsViewModel,
    )

_INTRO = (
    "Add a Binance key and the app finds out which environment it belongs to: "
    "mainnet, Spot Testnet or Futures Testnet. A mainnet key goes in the "
    "operating system's keyring; a testnet key in secrets.local.json (not "
    "tracked in git). A key that can withdraw funds is refused. A key is saved "
    "when you add, replace or remove it: OK and Apply have nothing to save here."
)
#: The State is not a column: a failure sentence is two hundred characters, and a column of the
#: dialog's minimum width gave it 75 px (`BOT-225`). It is a line of its own under each venue, the
#: page's full width.
_COLUMNS = ("Venue", "Key")
#: A key the exchange accepted, and one it did not (`EPIC-043E`); the words stay beside the icon.
CONNECTED_LOOK = StateLook("circle-check-big", Tone.POSITIVE)
ERROR_LOOK = StateLook("circle-x", Tone.NEGATIVE)


class _RowWidgets:
    """The widgets of one venue's row, updated in place."""

    def __init__(self, venue: TradingVenue) -> None:
        self.venue = venue
        self.title = plain_label()
        self.key = plain_label()
        self.state = StateBadge(f"lblKeyState_{venue.name}", wrap=True)
        self.replace = QPushButton()
        self.replace.setObjectName(f"btnReplaceKey_{venue.name}")
        self.remove = QPushButton("Remove")
        self.remove.setObjectName(f"btnRemoveKey_{venue.name}")


class TradingSettingsView(BaseView):
    """@brief The Trading page of Tools → Options (`EPIC-033E`): one row per
    venue and the actions on a key (`BUG-176`)."""

    #: The Options dialog closed and let go of this page (not a switch to another page):
    #: whatever the page was waiting for is no longer wanted (`BOT-224`).
    dialogClosed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: dict[TradingVenue, _RowWidgets] = {}
        self._build_ui()

    def set_view_model(self, view_model: TradingSettingsViewModel) -> None:
        self._add_key_button.clicked.connect(view_model.requestAddKey)
        self._check_button.clicked.connect(view_model.requestCheckConnections)
        self._public_ip_button.clicked.connect(view_model.requestShowPublicIp)
        self._copy_ip_button.clicked.connect(
            lambda: _copy_to_clipboard(view_model.publicIp)
        )
        view_model.publicIpChanged.connect(lambda: self._apply_public_ip(view_model))
        view_model.rowsChanged.connect(lambda: self._apply_rows(view_model))
        view_model.busyChanged.connect(lambda: self._apply_busy(view_model))
        view_model.statusChanged.connect(lambda: self._apply_status(view_model))
        self._apply_rows(view_model)
        self._apply_busy(view_model)
        self._apply_status(view_model)
        self._apply_public_ip(view_model)

    def event(self, event: QEvent) -> bool:
        """The Engine's `OptionsDialog.done()` takes every page out of the dialog
        (`setParent(None)`) before it hides it, so a hide event cannot tell a close
        from a switch to another page; being let go of can."""
        handled = super().event(event)
        if event.type() == QEvent.Type.ParentChange and self.parent() is None:
            self.dialogClosed.emit()
        return handled

    def ask_for_key(self, hint: str) -> tuple[str, str] | None:
        """Asks for a key and a secret in a modal dialog; `None` when cancelled."""
        dialog = AddKeyDialog(hint, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.take_entry()

    def _apply_rows(self, view_model: TradingSettingsViewModel) -> None:
        for row in view_model.rows:
            widgets = self._rows.get(row.venue) or self._add_row(row.venue, view_model)
            widgets.title.setText(row.title)
            widgets.key.setText(row.key)
            widgets.state.show_state(
                _worded(row.state, row.state_kind is StateKind.ERROR), _look(row)
            )
            widgets.replace.setText("Replace…" if row.has_key else "Add…")
            widgets.replace.setEnabled(row.editable and not view_model.busy)
            widgets.remove.setEnabled(
                row.has_key and row.editable and not view_model.busy
            )

    def _add_row(
        self, venue: TradingVenue, view_model: TradingSettingsViewModel
    ) -> _RowWidgets:
        widgets = _RowWidgets(venue)
        grid_row = 1 + 2 * len(self._rows)
        self._grid.addWidget(widgets.title, grid_row, 0)
        self._grid.addWidget(widgets.key, grid_row, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(widgets.replace)
        buttons.addWidget(widgets.remove)
        self._grid.addLayout(buttons, grid_row, 2)
        self._grid.addWidget(widgets.state, grid_row + 1, 0, 1, len(_COLUMNS) + 1)
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
        self._public_ip_button.setEnabled(idle)
        self._apply_rows(view_model)

    def _apply_status(self, view_model: TradingSettingsViewModel) -> None:
        self._status_label.setText(
            _worded(view_model.statusMessage, view_model.statusIsError)
        )

    def _apply_public_ip(self, view_model: TradingSettingsViewModel) -> None:
        found = bool(view_model.publicIp)
        self._ip_caption.setVisible(found)
        self._ip_value.setVisible(found)
        self._copy_ip_button.setVisible(found)
        self._ip_advice.setVisible(found)
        self._ip_value.setText(view_model.publicIp)
        self._ip_problem.setText(_worded(view_model.publicIpProblem, True))
        self._ip_problem.setVisible(bool(view_model.publicIpProblem))

    def _build_public_ip_block(self) -> QVBoxLayout:
        """The address read-out: selectable text, a Copy button, and one line on
        where it goes. Hidden until a lookup finds one (`BOT-224`)."""
        block = QVBoxLayout()
        row = QHBoxLayout()
        self._ip_caption = plain_label(CAPTION)
        self._ip_value = plain_label()
        self._ip_value.setObjectName("lblPublicIp")
        self._ip_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._copy_ip_button = QPushButton("Copy")
        self._copy_ip_button.setObjectName("btnCopyPublicIp")
        row.addWidget(self._ip_caption)
        row.addWidget(self._ip_value)
        row.addWidget(self._copy_ip_button)
        row.addStretch(1)
        block.addLayout(row)
        self._ip_advice = plain_label(ADVICE)
        self._ip_advice.setObjectName("lblPublicIpAdvice")
        self._ip_advice.setWordWrap(True)
        block.addWidget(self._ip_advice)
        self._ip_problem = plain_label()
        self._ip_problem.setObjectName("lblPublicIpProblem")
        self._ip_problem.setWordWrap(True)
        block.addWidget(self._ip_problem)
        return block

    def _build_ui(self) -> None:
        # The page scrolls once, at itself: a scroll area asks its content's `heightForWidth`, so
        # a wrapped sentence has the height its text needs at the page's width instead of the one
        # line a dialog's minimum size counts (`BOT-225`; as `PlanColumn`, `BUG-246`); it keeps the
        # width its content needs, so nothing is cut at the side.
        body = QWidget()
        scroll = ContentWidthScrollArea()
        scroll.setObjectName("scrollTradingSettings")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        intro = plain_label(_INTRO)
        intro.setObjectName("lblTradingSettingsIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(14)
        self._grid.setVerticalSpacing(12)
        self._grid.setColumnStretch(1, 1)
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
        self._public_ip_button = QPushButton("Show public IP")
        self._public_ip_button.setObjectName("btnShowPublicIp")
        buttons.addWidget(self._public_ip_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addLayout(self._build_public_ip_block())

        self._busy_label: QLabel = plain_label()
        self._busy_label.setObjectName("lblTradingSettingsBusy")
        layout.addWidget(self._busy_label)

        self._status_label = plain_label()
        self._status_label.setObjectName("lblTradingSettingsStatus")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)


def _copy_to_clipboard(text: str) -> None:
    QGuiApplication.clipboard().setText(text)


def _look(row: KeyRow) -> StateLook | None:
    """The icon and tone beside a venue's state: a key that works, or one that does not. A venue
    with no key, or one not checked yet, has only its words."""
    if row.state_kind is StateKind.ERROR:
        return ERROR_LOOK
    return CONNECTED_LOOK if row.state_kind is StateKind.CONNECTED else None


def _worded(message: str, is_error: bool) -> str:
    """An error is named in words, never by weight or colour alone
    (`ui-presentation-rule.md` §1)."""
    return f"Error: {message}" if is_error and message else message
