"""`EPIC-028J` — one history tab: the page's rows, which pairs it read,
what the venue cannot show, and the pager.

@details One class for both histories; the table model passed in is the only
difference. Read-only: a past order or fill has nothing to act on. The
notices sit above the rows in plain words (`EPIC-028Q`); a tooltip would hide
exactly the sentence that says some fills are missing.
"""

from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_view import (
    HistoryView,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import (
    SORT_ROLE,
    RowTableModel,
)

_LOADING_TEXT = "Reading the history..."


class HistoryPanel[TRow](QWidget):  # base-exempt: a container, not a surface
    """@brief One page of one history, with its scope and its notices."""

    #: The zero-based page the user asked for.
    pageRequested = Signal(int)

    def __init__(
        self,
        model: RowTableModel[TRow],
        name: str,
        parent: QWidget | None = None,
    ) -> None:
        """@param name The tab's name in `objectName`s, e.g. "OrderHistory"."""
        super().__init__(parent)
        self._model = model
        model.setParent(self)
        self._page = 0
        proxy = QSortFilterProxyModel(self)
        proxy.setSourceModel(model)
        proxy.setSortRole(SORT_ROLE)

        self._scope = QLabel()
        self._scope.setObjectName(f"lbl{name}Scope")
        self._scope.setWordWrap(True)
        self._notices = QLabel()
        self._notices.setObjectName(f"lbl{name}Notices")
        self._notices.setWordWrap(True)
        self._notices.hide()

        self._table = QTableView()
        self._table.setObjectName(f"tbl{name}")
        self._table.setModel(proxy)
        # Newest first is the order the venue's page arrives in; sorting is
        # off until a header is clicked, so that order is what shows.
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setSortIndicatorShown(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self._empty = QLabel(_LOADING_TEXT)
        self._empty.setObjectName(f"lbl{name}Empty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._body = QStackedWidget()
        self._body.addWidget(self._empty)
        self._body.addWidget(self._table)

        self._previous = QPushButton("Previous")
        self._previous.setObjectName(f"btn{name}Previous")
        self._previous.clicked.connect(lambda: self.pageRequested.emit(self._page - 1))
        self._next = QPushButton("Next")
        self._next.setObjectName(f"btn{name}Next")
        self._next.clicked.connect(lambda: self.pageRequested.emit(self._page + 1))
        self._page_label = QLabel()
        self._page_label.setObjectName(f"lbl{name}Page")
        pager = QHBoxLayout()
        pager.addStretch(1)
        pager.addWidget(self._previous)
        pager.addWidget(self._page_label)
        pager.addWidget(self._next)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._scope)
        layout.addWidget(self._notices)
        layout.addWidget(self._body, 1)
        layout.addLayout(pager)
        self.show_loading()

    def show_loading(self) -> None:
        """While a page is being read: the pager waits with it."""
        self._show_message(_LOADING_TEXT)

    def show_error(self, text: str) -> None:
        self._show_message(text)

    def show_view(self, view: HistoryView[TRow]) -> None:
        self._page = view.page
        self._model.set_rows(view.rows)
        self._scope.setText(view.scope_text)
        self._notices.setText("\n".join(view.notices))
        self._notices.setVisible(bool(view.notices))
        self._page_label.setText(view.page_text)
        self._previous.setEnabled(view.has_previous)
        self._next.setEnabled(view.has_next)
        if view.rows:
            self._body.setCurrentWidget(self._table)
        else:
            self._empty.setText("No rows in this span.")
            self._body.setCurrentWidget(self._empty)

    @property
    def table(self) -> QTableView:
        return self._table

    def _show_message(self, text: str) -> None:
        self._empty.setText(text)
        self._body.setCurrentWidget(self._empty)
        self._previous.setEnabled(False)
        self._next.setEnabled(False)
