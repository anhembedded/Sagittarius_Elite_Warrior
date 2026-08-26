"""EPIC-006E: `BackTestTradeLogs.qml` -> QtWidgets.

Bottom pane of the Backtest screen: a `DynamicTabBarWidget` switching
between the paginated Trade Logs table and the Backtest execution log
(`AppLogPanel`, already ported in EPIC-005E/EPIC-006D). Rows rebuild
wholesale on every `tradeLogRowsChanged` — same "rebuild, don't diff"
precedent `DevBoardPanel._rebuild_script_rows()` established (EPIC-006D):
a page tops out at 20 rows, so a full rebuild is cheap and keeps this file
simple.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.app_log_panel import (
    AppLogPanel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    StyleRole,
    Tab,
    TabBar,
    apply_role,
)

from .backtest_widgets import with_alpha

if TYPE_CHECKING:
    from .backtest_view_model import BackTestViewModel

_FILTER_TABS = [
    ("all", "Tất cả"),
    ("long", "Mua (LONG)"),
    ("short", "Bán (SHORT)"),
    ("win", "Lệnh thắng"),
    ("loss", "Lệnh thua"),
]

#: (stretch, alignment) per column — mirrors BackTestTradeLogs.qml's
#: col1..col6Width proportions (17/8/28/18/16/13 %).
_COLUMNS = (17, 8, 28, 18, 16, 13)
_HEADERS = (
    "STT / THỜI GIAN",
    "LOẠI",
    "GIÁ VÀO  ➔  GIÁ THOÁT",
    "QUY MÔ / KHỐI LƯỢNG",
    "LÃI / LỖ RÒNG",
    "RETURN",
)


class _FilterTabButton(QPushButton):
    def __init__(self, value: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.value = value
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(26)
        self.set_active(False)

    def set_active(self, active: bool) -> None:
        self.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.STATE_HOVER_BG if active else 'transparent'}; "
            f"border: 1px solid {Palette.STATE_NAV_BORDER if active else 'transparent'}; border-radius: 6px; "
            f"color: {Palette.TEXT_PRIMARY if active else Palette.MUTED}; font-size: 11px; "
            f"font-weight: {'bold' if active else 'normal'}; padding: 0 10px; }}"
        )


class _TradeLogRowWidget(QFrame):  # base-exempt: excluded from DataRow by design
    """One trade row + its collapsible detail panel — port of
    `BackTestTradeLogs.qml`'s `ListView` delegate `Column`.

    **Deliberately not migrated to the engine's `DataRow`.** That widget's
    own docstring excludes this one by name, and re-reading this class
    against that reasoning confirms it: the summary is a clickable
    `QPushButton`, three of its columns stack two differently-styled lines,
    two cells are recoloured badges, it owns a collapsible detail pane of
    three further columns, and it emits a toggle signal. Fitting it would
    need a per-cell widget factory, an expandable-body hook and a click
    signal on `DataRow` — at which point every part of the base is
    overridden and the base carries parameters that exist for one caller.

    `DataRow` still covers the other three row shapes in this app."""

    toggled = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = -1
        self._expanded = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._summary_btn = QPushButton()
        self._summary_btn.setObjectName("rowTradeLog")
        self._summary_btn.setFlat(True)
        self._summary_btn.setFixedHeight(44)
        self._summary_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._summary_btn.clicked.connect(lambda: self.toggled.emit(self._index))
        row = QHBoxLayout(self._summary_btn)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(8)

        col1 = QVBoxLayout()
        col1.setSpacing(2)
        self._position_label = QLabel()
        self._position_label.setStyleSheet(
            f"color: {Palette.TEXT_PRIMARY}; font-size: 11px; font-weight: bold; border: none; background: transparent;"
        )
        col1.addWidget(self._position_label)
        self._entry_time_label = QLabel()
        self._entry_time_label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 10px; border: none; background: transparent;"
        )
        col1.addWidget(self._entry_time_label)
        row.addLayout(col1, _COLUMNS[0])

        self._side_badge = QLabel()
        self._side_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._side_badge.setFixedHeight(20)
        row.addWidget(self._side_badge, _COLUMNS[1])

        col3 = QVBoxLayout()
        col3.setSpacing(2)
        price_row = QHBoxLayout()
        price_row.setSpacing(6)
        self._price_label = QLabel()
        self._price_label.setStyleSheet(
            f"color: {Palette.TEXT_PRIMARY}; font-size: 11px; font-weight: bold; border: none; background: transparent;"
        )
        price_row.addWidget(self._price_label)
        self._price_diff_label = QLabel()
        self._price_diff_label.setStyleSheet(
            "font-size: 10px; font-weight: bold; border: none; background: transparent;"
        )
        price_row.addWidget(self._price_diff_label)
        price_row.addStretch(1)
        col3.addLayout(price_row)
        self._exit_time_label = QLabel()
        self._exit_time_label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 10px; border: none; background: transparent;"
        )
        col3.addWidget(self._exit_time_label)
        row.addLayout(col3, _COLUMNS[2])

        col4 = QVBoxLayout()
        col4.setSpacing(2)
        self._size_label = QLabel()
        self._size_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._size_label.setStyleSheet(
            f"color: {Palette.TEXT_PRIMARY}; font-size: 11px; font-weight: bold; border: none; background: transparent;"
        )
        col4.addWidget(self._size_label)
        self._qty_label = QLabel()
        self._qty_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._qty_label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 10px; border: none; background: transparent;"
        )
        col4.addWidget(self._qty_label)
        row.addLayout(col4, _COLUMNS[3])

        pnl_wrap = QHBoxLayout()
        pnl_wrap.addStretch(1)
        self._pnl_badge = QLabel()
        self._pnl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pnl_badge.setFixedHeight(24)
        pnl_wrap.addWidget(self._pnl_badge)
        row.addLayout(pnl_wrap, _COLUMNS[4])

        self._return_label = QLabel()
        self._return_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._return_label.setStyleSheet(
            "font-size: 11px; font-weight: bold; border: none; background: transparent;"
        )
        row.addWidget(self._return_label, _COLUMNS[5])

        outer.addWidget(self._summary_btn)

        self._detail = QFrame()
        self._detail.setObjectName("detailTradeLog")
        # Scoped by objectName: unscoped, the top border it draws as a
        # separator would repeat on every one of the three detail columns
        # inside it.
        self._detail.setStyleSheet(
            f"#detailTradeLog {{ background-color: {Palette.BG}; "
            f"border-top: 1px solid {Palette.STATE_NAV_BORDER}; }}"
        )
        detail_layout = QHBoxLayout(self._detail)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(20)
        self._entry_reason_label = self._detail_column(detail_layout, "LÝ DO VÀO LỆNH")
        self._exit_reason_label = self._detail_column(detail_layout, "LÝ DO THOÁT LỆNH")
        self._metrics_column, self._metrics_label = self._detail_metrics_column(
            detail_layout
        )
        outer.addWidget(self._detail)
        self._detail.setVisible(False)

    def _detail_column(self, parent_layout: QHBoxLayout, heading: str) -> QLabel:
        column = QVBoxLayout()
        column.setSpacing(4)
        title = QLabel(heading)
        title.setStyleSheet(
            f"color: {Palette.ACCENT}; font-size: 9px; font-weight: bold; letter-spacing: 0.5px; border: none; background: transparent;"
        )
        column.addWidget(title)
        body = QLabel()
        body.setWordWrap(True)
        body.setStyleSheet(
            f"color: {Palette.TEXT_PRIMARY}; font-size: 11px; border: none; background: transparent;"
        )
        column.addWidget(body)
        parent_layout.addLayout(column, 1)
        return body

    def _detail_metrics_column(
        self, parent_layout: QHBoxLayout
    ) -> tuple[QVBoxLayout, QLabel]:
        column = QVBoxLayout()
        column.setSpacing(4)
        title = QLabel("CHỈ SỐ ĐÁNH GIÁ & THỜI LƯỢNG")
        title.setStyleSheet(
            f"color: {Palette.ACCENT}; font-size: 9px; font-weight: bold; letter-spacing: 0.5px; border: none; background: transparent;"
        )
        column.addWidget(title)
        duration_label = QLabel()
        duration_label.setStyleSheet(
            f"color: {Palette.TEXT_PRIMARY}; font-size: 11px; font-weight: bold; border: none; background: transparent;"
        )
        column.addWidget(duration_label)
        parent_layout.addLayout(column, 1)
        return column, duration_label

    def apply_row(self, index: int, row: dict, row_number: int) -> None:
        self._index = index
        self._summary_btn.setObjectName(f"rowTradeLog_{index}")
        self._detail.setObjectName(f"detailTradeLog_{index}")
        self._summary_btn.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.BG_CARD if row_number % 2 == 0 else Palette.BG_CARD_HEADER}; "
            f"border: none; }} QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }}"
        )
        self._position_label.setText(row.get("positionLabel", ""))
        self._entry_time_label.setText(row.get("entryTimeText", ""))

        side_text = row.get("sideText") or "LONG"
        is_short = side_text == "SHORT"
        side_color = Palette.DANGER if is_short else Palette.SUCCESS
        self._side_badge.setText(side_text)
        self._side_badge.setStyleSheet(
            # Ground is uniform; long-vs-short is carried by `side_color` on the
            # text and border, the same split EPIC-007B's Banner makes.
            f"color: {side_color}; background-color: {Palette.BG_CARD_HEADER}; "
            f"border: 1px solid {side_color}; border-radius: 4px; font-size: 10px; font-weight: bold;"
        )

        self._price_label.setText(
            f"{row.get('entryPriceText', '')}  ➔  {row.get('exitPriceText', '')}"
        )
        diff_text = row.get("priceDiffText", "")
        self._price_diff_label.setText(diff_text)
        self._price_diff_label.setVisible(bool(diff_text))
        diff_color = row.get("priceDiffColor") or Palette.MUTED
        self._price_diff_label.setStyleSheet(
            f"color: {diff_color}; font-size: 10px; font-weight: bold; border: none; background: transparent;"
        )
        self._exit_time_label.setText(f"Thoát: {row.get('exitTimeText', '')}")

        self._size_label.setText(row.get("positionSizeText", ""))
        self._qty_label.setText(row.get("quantityText", ""))

        pnl_color = row.get("pnlColor") or Palette.MUTED
        self._pnl_badge.setText(row.get("pnlText", ""))
        self._pnl_badge.setStyleSheet(
            f"color: {pnl_color}; background-color: {with_alpha(pnl_color, 0.12)}; "
            f"border: 1px solid {with_alpha(pnl_color, 0.4)}; border-radius: 4px; "
            f"font-size: 11px; font-weight: bold;"
        )
        self._return_label.setText(row.get("returnText", ""))
        self._return_label.setStyleSheet(
            f"color: {pnl_color}; font-size: 11px; font-weight: bold; border: none; background: transparent;"
        )

        self._entry_reason_label.setText(row.get("entryReasonText", ""))
        self._exit_reason_label.setText(row.get("exitReasonText", ""))
        duration_text = f"Thời lượng: {row.get('durationText', '')}"
        for item in row.get("metadataItems", []) or []:
            duration_text += f"\n{item.get('label', '')}: {item.get('value', '')}"
        self._metrics_label.setText(duration_text)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._detail.setVisible(expanded)


class BackTestTradeLogsPanel(QWidget):  # base-exempt: screen region, not a card
    """Port of `BackTestTradeLogs.qml`.

    **Not a `Surface`**: it is the bottom region of the screen, holding the
    tab bar, the table and the log panel. The cards are inside it."""

    #: BOT-090's usable-height floor, recomputed in Python instead of read
    #: back from a QML `implicitHeight` property (no QML root exists
    #: anymore) — same constants (`rowHeight`, `minVisibleRows`) the QML
    #: used, so the floor is unchanged.
    ROW_HEIGHT = 44
    MIN_VISIBLE_ROWS = 5

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._expanded_rows: dict[int, bool] = {}
        self.setStyleSheet(
            f"{type(self).__name__} {{ background-color: {Palette.BG}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        self._tab_bar = TabBar()
        self._tab_bar.setObjectName("bottomTabBar")
        self._tab_bar.tab_selected.connect(self._on_tab_selected)
        outer.addWidget(self._tab_bar)

        self._trades_tab = self._build_trades_tab()
        outer.addWidget(self._trades_tab, 1)

        self._log_panel = AppLogPanel("NHẬT KÝ BACKTEST")
        self._log_panel.setObjectName("backtestLogPanel")
        self._log_panel.set_log_model(view_model.log_model)
        outer.addWidget(self._log_panel, 1)

        self._wire_view_model()
        self._sync_all()

    # ------------------------------------------------------------------ #
    # Trades tab
    # ------------------------------------------------------------------ #

    def _build_trades_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("tradeLogsTabContent")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        toolbar = QWidget()
        toolbar.setObjectName("toolbarRow")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(14)

        filters = QWidget()
        filters.setObjectName("tradeLogFilterTabs")
        filters_layout = QHBoxLayout(filters)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(4)
        self._filter_buttons: list[_FilterTabButton] = []
        for value, label in _FILTER_TABS:
            btn = _FilterTabButton(value, label)
            btn.setObjectName(f"tabTradeLogFilter_{value}")
            btn.clicked.connect(lambda _=False, v=value: self._on_filter_clicked(v))
            filters_layout.addWidget(btn)
            self._filter_buttons.append(btn)
        toolbar_layout.addWidget(filters)
        toolbar_layout.addStretch(1)

        self._search_field = QLineEdit()
        self._search_field.setObjectName("txtTradeLogSearch")
        self._search_field.setPlaceholderText("🔍  Tìm theo mã, ngày...")
        self._search_field.setFixedSize(200, 28)
        self._search_field.setStyleSheet(
            f"background-color: {Palette.BG_CARD_HEADER}; border: 1px solid {Palette.STATE_HOVER_BG}; border-radius: 6px; "
            f"color: {Palette.TEXT_PRIMARY}; font-size: 11px; padding: 0 6px;"
        )
        self._search_field.textEdited.connect(self._on_search_edited)
        toolbar_layout.addWidget(self._search_field)

        self._btn_export = QPushButton("Export")
        self._btn_export.setObjectName("btnTradeLogExport")
        self._btn_export.setFixedHeight(28)
        self._btn_export.setIcon(
            get_icon_loader().get_icon("download", Palette.ACCENT, 12)
        )
        self._btn_export.setStyleSheet(
            f"background-color: {Palette.BG_CARD_HEADER}; border: 1px solid {Palette.STATE_NAV_BORDER}; border-radius: 6px; "
            f"color: {Palette.TEXT_PRIMARY}; font-size: 11px; font-weight: bold; padding: 0 10px;"
        )
        self._btn_export.clicked.connect(self._vm.requestTradeLogExport)
        toolbar_layout.addWidget(self._btn_export)

        layout.addWidget(toolbar)

        table_container = QFrame()
        apply_role(table_container, StyleRole.SURFACE)
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        self._table_header = self._build_table_header()
        table_layout.addWidget(self._table_header)

        self._rows_scroll = QScrollArea()
        self._rows_scroll.setWidgetResizable(True)
        self._rows_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._rows_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._rows_container = QWidget()
        self._rows_container.setObjectName("listTradeLogRows")
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._rows_layout.addStretch(1)
        self._rows_scroll.setWidget(self._rows_container)
        table_layout.addWidget(self._rows_scroll, 1)

        self._empty_label = QLabel("Chưa có dữ liệu lệnh giao dịch")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 12px;")
        table_layout.addWidget(self._empty_label)

        self._pagination_row = self._build_pagination_row()
        table_layout.addWidget(self._pagination_row)

        layout.addWidget(table_container, 1)
        return tab

    def _build_table_header(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(34)
        # Scoped by hand rather than given `TABLE_HEADER`: that role rounds
        # its corners, and this strip sits flush inside a card that already
        # rounds them, with a separator line along its bottom edge instead.
        header.setStyleSheet(
            f"QFrame {{ background-color: {Palette.BG_CARD_HEADER}; "
            f"border-bottom: 1px solid {Palette.BORDER}; }}"
        )
        row = QHBoxLayout(header)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(8)
        alignments = (
            Qt.AlignmentFlag.AlignLeft,
            Qt.AlignmentFlag.AlignCenter,
            Qt.AlignmentFlag.AlignLeft,
            Qt.AlignmentFlag.AlignRight,
            Qt.AlignmentFlag.AlignRight,
            Qt.AlignmentFlag.AlignRight,
        )
        for text, stretch, alignment in zip(
            _HEADERS, _COLUMNS, alignments, strict=True
        ):
            label = QLabel(text)
            label.setAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
            label.setStyleSheet(
                f"color: {Palette.MUTED}; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;"
            )
            row.addWidget(label, stretch)
        return header

    def _build_pagination_row(self) -> QWidget:
        row_widget = QWidget()
        row_widget.setFixedHeight(34)
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)

        self._btn_prev_page = QPushButton("‹  Trang trước")
        self._btn_prev_page.setObjectName("btnTradeLogPrevPage")
        self._btn_prev_page.setFixedHeight(26)
        self._btn_prev_page.clicked.connect(
            lambda: setattr(
                self._vm, "tradeLogCurrentPage", self._vm.tradeLogCurrentPage - 1
            )
        )
        row.addWidget(self._btn_prev_page)

        self._page_label = QLabel()
        self._page_label.setFixedHeight(22)
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setStyleSheet(
            f"background-color: {Palette.STATE_IDLE_BG}; border-radius: 4px; color: {Palette.ACCENT}; "
            f"font-size: 11px; font-weight: bold; padding: 0 8px;"
        )
        row.addWidget(self._page_label)

        self._btn_next_page = QPushButton("Trang sau  ›")
        self._btn_next_page.setObjectName("btnTradeLogNextPage")
        self._btn_next_page.setFixedHeight(26)
        self._btn_next_page.clicked.connect(
            lambda: setattr(
                self._vm, "tradeLogCurrentPage", self._vm.tradeLogCurrentPage + 1
            )
        )
        row.addWidget(self._btn_next_page)

        row.addStretch(1)
        return row_widget

    # ------------------------------------------------------------------ #
    # ViewModel wiring
    # ------------------------------------------------------------------ #

    def _wire_view_model(self) -> None:
        vm = self._vm
        vm.activeBottomTabChanged.connect(self._sync_active_tab)
        vm.tradeLogFilterChanged.connect(self._sync_filters)
        vm.tradeLogSearchTextChanged.connect(self._sync_search)
        vm.tradeLogRowsChanged.connect(self._sync_rows)
        vm.tradeLogRowsChanged.connect(self._sync_tab_badges)
        vm.tradeLogCurrentPageChanged.connect(self._sync_pagination)
        vm.logModel.countChanged.connect(self._sync_tab_badges)
        vm.isConfigDirtyChanged.connect(self._sync_dirty_opacity)

    def _sync_all(self) -> None:
        self._sync_active_tab()
        self._sync_filters()
        self._sync_search()
        self._sync_rows()
        self._sync_tab_badges()
        self._sync_pagination()
        self._sync_dirty_opacity()

    def _sync_active_tab(self) -> None:
        is_logs = self._vm.activeBottomTab == "logs"
        self._trades_tab.setVisible(not is_logs)
        self._log_panel.setVisible(is_logs)
        self._tab_bar.set_current_id("logs" if is_logs else "trades")

    def _on_tab_selected(self, index: int, tab_id: str) -> None:
        self._vm.setActiveBottomTab(tab_id)

    def _sync_tab_badges(self) -> None:
        total = self._vm.tradeLogTotalCount
        log_count = self._vm.logModel.rowCount()
        self._tab_bar.set_tabs(
            [
                Tab("trades", "DANH SÁCH LỆNH", f"{total} LỆNH"),
                Tab("logs", "NHẬT KÝ BACKTEST", f"{log_count} EVENTS"),
            ]
        )
        self._sync_active_tab()

    def _sync_filters(self) -> None:
        current = self._vm.tradeLogFilter
        for btn in self._filter_buttons:
            btn.set_active(btn.value == current)

    def _on_filter_clicked(self, value: str) -> None:
        self._vm.tradeLogFilter = value

    def _sync_search(self) -> None:
        if self._search_field.text() != self._vm.tradeLogSearchText:
            self._search_field.setText(self._vm.tradeLogSearchText)

    def _on_search_edited(self, text: str) -> None:
        self._vm.tradeLogSearchText = text

    def _sync_rows(self) -> None:
        rows = self._vm.tradeLogRows
        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        has_rows = bool(rows)
        self._empty_label.setVisible(not has_rows)
        self._rows_scroll.setVisible(has_rows)

        for row_number, row in enumerate(rows):
            index = int(row.get("index", row_number))
            row_widget = _TradeLogRowWidget()
            row_widget.toggled.connect(self._on_row_toggled)
            row_widget.apply_row(index, row, row_number)
            row_widget.set_expanded(self._expanded_rows.get(index, False))
            self._rows_layout.insertWidget(self._rows_layout.count() - 1, row_widget)

    def _on_row_toggled(self, index: int) -> None:
        self._expanded_rows[index] = not self._expanded_rows.get(index, False)
        for i in range(self._rows_layout.count() - 1):
            widget = self._rows_layout.itemAt(i).widget()
            if isinstance(widget, _TradeLogRowWidget) and widget._index == index:
                widget.set_expanded(self._expanded_rows[index])
                break

    def _sync_pagination(self) -> None:
        vm = self._vm
        visible = vm.tradeLogTotalPages > 1
        self._pagination_row.setVisible(visible)
        self._btn_prev_page.setEnabled(vm.tradeLogCurrentPage > 1)
        self._btn_next_page.setEnabled(vm.tradeLogCurrentPage < vm.tradeLogTotalPages)
        self._page_label.setText(
            f"Trang {vm.tradeLogCurrentPage} / {vm.tradeLogTotalPages}"
        )

    def _sync_dirty_opacity(self) -> None:
        # Qt Widgets has no CSS `opacity` for arbitrary QFrame content;
        # QGraphicsOpacityEffect is the real mechanism, applied lazily here
        # to avoid paying for it on every screen that never goes dirty.
        from PySide6.QtWidgets import QGraphicsOpacityEffect

        effect = self._trades_tab.graphicsEffect()
        if self._vm.isConfigDirty:
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(self._trades_tab)
                self._trades_tab.setGraphicsEffect(effect)
            effect.setOpacity(0.6)
        elif effect is not None:
            self._trades_tab.setGraphicsEffect(None)

    def minimum_usable_height(self) -> int:
        """Port of `BackTestTradeLogs.qml`'s `minimumUsableHeight` — the
        BOT-090 floor `BackTestView._bind_trade_log_minimum_height()` (or
        its EPIC-006E2 QtWidgets successor) applies via
        `setMinimumHeight()`."""
        return (
            self._tab_bar.sizeHint().height()
            + 10
            + self._table_header.height()
            + self.MIN_VISIBLE_ROWS * self.ROW_HEIGHT
            + self._pagination_row.sizeHint().height()
            + 24
        )
