"""`EPIC-029F` — creating a bot: kind, then venue, then symbol; nothing more.

`BOT-150` (the user's rule, 2026-10-04): creating a bot asks the least. The
parameters are not asked here; the bot is saved as a DRAFT without them and
selected, and the user sets them in its detail panel, where the planner has
read the symbol's numbers and can suggest a range. They can be changed again
whenever the bot is not running (DRAFT or STOPPED, the lifecycle's EDIT).

The symbol is typed, never taken from a chart, so a bot never trades a pair
because a chart happened to show it. Only enabled Spot venues are offered:
the Grid is a Spot kind. Nothing is placed; Cancel discards every field.
Injectable (`AskNewBot`) so a test creates a bot without a modal dialog.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_panels import (
    KIND_TITLES,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: The command, or `None` when the user cancelled.
type AskNewBot = Callable[
    [Sequence[str], Sequence[TradingVenue]], CreateBotCommand | None
]

CREATE_BUTTON_TEXT = "Create bot"
NO_SPOT_VENUE = "No Spot venue is enabled. Enable one in Settings first."
PARAMETERS_HINT = (
    "The parameters are set after the bot is created, and can be changed "
    "whenever it is not running."
)


class NewBotDialog(QDialog):
    """@brief Collects one new bot's definition."""

    def __init__(
        self,
        kinds: Sequence[str],
        venues: Sequence[TradingVenue],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New bot")
        self.kind = QComboBox()
        self.kind.setObjectName("cmbNewBotKind")
        for kind_id in kinds:
            self.kind.addItem(KIND_TITLES.get(kind_id, kind_id), kind_id)
        self.venue = QComboBox()
        self.venue.setObjectName("cmbNewBotVenue")
        for venue in venues:
            self.venue.addItem(venue.value, venue)
        self.symbol = QLineEdit()
        self.symbol.setObjectName("editNewBotSymbol")
        self.symbol.setPlaceholderText("e.g. BTCUSDT")
        self.name = QLineEdit()
        self.name.setObjectName("editNewBotName")
        self.problem = QLabel(NO_SPOT_VENUE if not venues else "")
        self.problem.setWordWrap(True)
        self.problem.setVisible(not venues)
        self.parameters_hint = QLabel(PARAMETERS_HINT)
        self.parameters_hint.setObjectName("lblNewBotParametersHint")
        self.parameters_hint.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.create_button: QPushButton = buttons.addButton(
            CREATE_BUTTON_TEXT, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.create_button.setObjectName("btnCreateBot")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow("Kind", self.kind)
        form.addRow("Venue", self.venue)
        form.addRow("Symbol", self.symbol)
        form.addRow("Name", self.name)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.problem)
        layout.addWidget(self.parameters_hint)
        layout.addWidget(buttons)
        self.symbol.textEdited.connect(self._sync_create)
        self.name.textEdited.connect(self._sync_create)
        self._sync_create()

    def command(self) -> CreateBotCommand:
        return CreateBotCommand(
            name=self.name.text().strip() or f"{self._symbol()} grid",
            kind=self.kind.currentData(),
            # `BUG-144`: Qt returns a `str`-based enum's item data as a plain
            # `str`; the member is rebuilt here, at the boundary that lost it.
            venue=TradingVenue(self.venue.currentData()),
            symbol=self._symbol(),
        )

    def _symbol(self) -> str:
        return self.symbol.text().strip().upper()

    def _sync_create(self) -> None:
        ready = (
            self.venue.count() > 0 and self.kind.count() > 0 and bool(self._symbol())
        )
        self.create_button.setEnabled(ready)
        self.create_button.setToolTip(
            "" if ready else "Choose a venue and type a symbol."
        )


def ask_new_bot_with_dialog(
    parent: QWidget, kinds: Sequence[str], venues: Sequence[TradingVenue]
) -> CreateBotCommand | None:
    dialog = NewBotDialog(kinds, venues, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.command()
