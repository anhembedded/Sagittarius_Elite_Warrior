"""One row of the backtest trade log."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
)

from ._trade_log_columns import _COLUMNS
from .backtest_widgets import with_alpha


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
