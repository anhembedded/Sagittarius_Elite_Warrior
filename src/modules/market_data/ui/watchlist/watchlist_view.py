"""The Watchlist screen (`BOT-019`) — a live `QTableView` of tracked symbols,
replacing the need to open a `ChartCard` per symbol just to see its current
price, % change and volume.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit.page_shell import PageShell
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit.style import semantic_colour
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from sagittarius_engine.extensions.pyside_mvc import BaseView

from .watchlist_table_model import WatchlistTableModel

_EMPTY_TEXT = "No symbols are tracked. Choose them in Tools → Options."


def _apply_tone(label: QLabel, name: str) -> None:
    """Colours `label` by a semantic tone chosen per instance at runtime —
    same idiom `market_data_settings_view.py`'s own `_apply_tone` already
    established for exactly this "status line, tone depends on outcome"
    case (`kit/style.py`'s documented escape hatch for what `apply_role()`
    cannot express). `QPalette`, never `setStyleSheet()`."""
    palette = QPalette(label.palette())
    palette.setColor(QPalette.ColorRole.WindowText, QColor(semantic_colour(name)))
    label.setPalette(palette)


class WatchlistView(BaseView):
    """@brief The Watchlist screen — a table of tracked symbols, updated live."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = WatchlistTableModel(self)
        # Columns, sorting and selection from the model's specs (`EPIC-033N`);
        # symbol ascending is the order a user finds a symbol in.
        self._spec_table = SpecTable(
            self.model, object_name="tblWatchlist", empty_text=_EMPTY_TEXT
        )
        self._spec_table.sort_by(WatchlistTableModel.column("symbol"))
        self.table = self._spec_table.view
        self._status_label = QLabel()
        self._status_label.setObjectName("lblWatchlistStatus")
        self._status_label.setWordWrap(True)

        self._shell = PageShell()
        self._shell.set_header(
            "Watchlist", "Live price, % change and volume for tracked symbols"
        )
        self._shell.set_workspace(self._spec_table.body)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._shell)

    def set_status(self, message: str, *, is_error: bool) -> None:
        """`SPEC-002` §4/§5 — every stream-owning screen must say so when
        `IMarketStream.start()` fails, the same way Dashboard/Trading
        already do; a Watchlist that only stays on its seeded `"—"` rows is
        indistinguishable from "no tick has arrived yet." Shown in
        `PageShell`'s context bar, which stays hidden until the first
        status arrives and never re-hides itself afterward — a live
        screen's last-known status is worth keeping visible, not just
        flashing once."""
        self._status_label.setText(message)
        _apply_tone(self._status_label, "danger" if is_error else "success")
        self._shell.set_context_bar(self._status_label)
