"""`EPIC-029F` — creating a bot: kind, venue, then symbol; nothing more.

`BOT-150` (the user's rule, 2026-10-04): creating a bot asks the least. The
parameters are not asked here; the bot is saved as a DRAFT without them and
selected, and the user sets them in its detail panel, where the planner has
read the symbol's numbers and can suggest a range. They can be changed again
whenever the bot is not running (DRAFT or STOPPED, the lifecycle's EDIT).

The symbol is chosen in the shared symbol picker over the Spot catalog (`BUG-155`),
never taken from a chart, so a bot never trades a pair because a chart happened
to show it. The Spot venues are offered whether or not one is enabled and one is
always preselected: Venue never blocks Create (`BUG-155`). A venue that is not
enabled is refused where it matters, at Start and in the planner. Nothing is
placed; Cancel discards every field. Injectable (`AskNewBot`) so a test creates
a bot without a modal dialog.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.new_bot_symbols import (
    NewBotSymbols,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_panels import (
    KIND_TITLES,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPickerOverlay,
)

#: The command, or `None` when the user cancelled.
type AskNewBot = Callable[
    [Sequence[str], Sequence[TradingVenue]], CreateBotCommand | None
]


def spot_venues_enabled_first(enabled: Collection[TradingVenue]) -> list[TradingVenue]:
    """Every Spot venue, the enabled ones first, so the preselected one is a
    venue the bot can start on whenever one is enabled (`BUG-155`)."""
    spot = [v for v in TradingVenue if v.market_type is MarketType.SPOT]
    return sorted(spot, key=lambda venue: venue not in enabled)


CREATE_BUTTON_TEXT = "Create bot"
VENUE_HINT = "Start needs the venue enabled in Tools > Options > Trading."
CHOOSE_SYMBOL_TEXT = "Choose symbol…"
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
        symbols: NewBotSymbols,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._symbols = symbols
        self._chosen = ""
        self._picker: SymbolPickerOverlay | None = None
        self.setWindowTitle("New bot")
        self.kind = QComboBox()
        self.kind.setObjectName("cmbNewBotKind")
        for kind_id in kinds:
            self.kind.addItem(KIND_TITLES.get(kind_id, kind_id), kind_id)
        self.venue = QComboBox()
        self.venue.setObjectName("cmbNewBotVenue")
        for venue in venues:
            self.venue.addItem(venue.display_name, venue)
        self.symbol = QPushButton(CHOOSE_SYMBOL_TEXT)
        self.symbol.setObjectName("btnNewBotSymbol")
        self.symbol.clicked.connect(self._open_picker)
        self.name = QLineEdit()
        self.name.setObjectName("editNewBotName")
        self.problem = plain_label()
        self.problem.setObjectName("lblNewBotProblem")
        self.problem.setWordWrap(True)
        self.problem.setVisible(False)
        symbols.catalog_failed.connect(self._show_catalog_problem)
        self.venue_hint = plain_label(VENUE_HINT)
        self.venue_hint.setObjectName("lblNewBotVenueHint")
        self.venue_hint.setWordWrap(True)
        self.parameters_hint = plain_label(PARAMETERS_HINT)
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
        layout.addWidget(self.venue_hint)
        layout.addWidget(self.parameters_hint)
        layout.addWidget(buttons)
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
        return self._chosen

    def _show_catalog_problem(self, message: str) -> None:
        self.problem.setText(f"Could not load the symbol list: {message}")
        self.problem.setVisible(True)

    def _open_picker(self) -> None:
        if self._picker is None:
            self._picker = self._build_picker()
        self._picker.open()

    def _build_picker(self) -> SymbolPickerOverlay:
        symbols = self._symbols
        picker = SymbolPickerOverlay(
            symbols.catalog_symbols,
            symbols.starred,
            symbols.recent,
            lambda: self._chosen,
            self,
        )
        picker.refresh_requested.connect(symbols.load_catalog)
        symbols.catalog_ready.connect(picker.refresh)
        picker.favourite_toggled.connect(self._toggle_favourite)
        picker.symbol_chosen.connect(self._symbol_picked)
        return picker

    def _toggle_favourite(self, symbol: str) -> None:
        self._symbols.toggle_star(symbol)
        if self._picker is not None:
            self._picker.refresh()

    def _symbol_picked(self, symbol: str) -> None:
        self._chosen = symbol.strip().upper()
        self._symbols.note_used(self._chosen)
        self.symbol.setText(self._chosen)
        self._sync_create()

    def _sync_create(self) -> None:
        ready = (
            self.venue.count() > 0 and self.kind.count() > 0 and bool(self._symbol())
        )
        self.create_button.setEnabled(ready)
        self.create_button.setToolTip("" if ready else "Choose a symbol.")


def ask_new_bot_with_dialog(
    parent: QWidget,
    kinds: Sequence[str],
    venues: Sequence[TradingVenue],
    symbols: NewBotSymbols,
) -> CreateBotCommand | None:
    dialog = NewBotDialog(kinds, venues, symbols, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.command()
