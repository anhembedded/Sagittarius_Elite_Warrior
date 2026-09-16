"""Backtest extended-metrics readout — a dialog with a table in it.

## Three renderings, and what each one answered

`ExtendedMetricsDialog` drew it as a `StatGrid` of cards. `EPIC-015` Phase 3
replaced that with `MetricsDetailPanel.qml` + `MetricsDetailVM` behind a
hand-written modal host, because the design wanted sections, verdict badges and
a profit-against-loss bar that the grid could not express. `EPIC-025` PR 4.3j
keeps every one of those and deletes the `.qml`: HLD §11.3 maps a readout like
this to *a dialog with a table*, and a `QTreeWidget` is the platform's own
answer to "rows under headings" — which is all the sections ever were.

Three things the QML version needed and this does not: a `QQuickWidget` host
supplying modality that `kit/DialogShell.qml` had no way to provide, a
`QObject` re-publishing every value as a `Property` for bindings to read, and a
`Theme` install so the scene could colour itself. `Overlay` is modal, the rules
are plain functions in `logic/metrics_detail_rules.py`, and the two colours
that carry meaning are written per item.

## What this file owns

The wiring, and only that: which callback feeds which control, what Copy puts
on the clipboard, and re-reading on every open. The grouping, the verdicts, the
bar's arithmetic and the clipboard's text are all `metrics_detail_rules.py`'s,
where they can be tested without a dialog.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.metrics_detail_rules import (
    GrossBar,
    MetricGroup,
    MetricRow,
    build_clipboard_text,
    build_footer,
    build_gross_bar,
    build_groups,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    Overlay,
    Tone,
    semantic_colour,
)

from .backtest_metrics_detail_source import BacktestMetricsDetailSource

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_TITLE = "BACKTEST DETAIL METRICS"
_METRIC_COLUMN = 0
_VALUE_COLUMN = 1
_VERDICT_COLUMN = 2
_COLUMNS = ("Metric", "Value", "Verdict")

#: The bar is drawn in permille rather than percent so a share of, say, 3.7%
#: does not collapse to 4 — the caption under it quotes two decimals.
_BAR_SCALE = 1000

#: The two semantic colours this file reads. Named `_COLOUR`, not `_TOKEN`,
#: because ruff's `S105` reads any `*_TOKEN = "..."` as a credential.
_GAIN_COLOUR = "success"
_LOSS_COLOUR = "danger"


def _tone_colour(tone: Tone) -> QColor | None:
    """A tone's colour, or `None` for "no verdict" — which leaves the row on
    the platform's own text colour."""
    if tone is Tone.POSITIVE:
        return QColor(semantic_colour(_GAIN_COLOUR))
    if tone is Tone.NEGATIVE:
        return QColor(semantic_colour(_LOSS_COLOUR))
    return None


class MetricsDetailDialogWidget(Overlay):
    """
    @brief Backtest's extended-metrics readout: a profit-against-loss bar, the
    metrics in sections, and one button that copies the lot as plain text.

    @details The composition root owns the adapter and the one piece of wiring
    a shared component could not: keeping the readout current. Two paths do it,
    the same dual coverage every version of this dialog has had —
    `statCardsChanged` while it is open or merely built, and `open_dialog()`
    once more on every open, so a change that landed while this object existed
    but was never shown is not silently missed.
    """

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        self._source = BacktestMetricsDetailSource(view_model)
        self._groups: tuple[MetricGroup, ...] = ()
        self._bar_data: GrossBar | None = None
        self._footer_value = ""
        super().__init__(_TITLE, parent=parent)
        self.setObjectName("backtestMetricsDetailDialog")
        self.resize(660, 700)

        self._build_bar_row()
        self._build_tree()
        self._build_footer()

        view_model.run_result.statCardsChanged.connect(self.refresh)
        self.refresh()

    # -- construction ------------------------------------------------------

    def _build_bar_row(self) -> None:
        row = QHBoxLayout()
        caption = QLabel("GROSS PROFIT VS GROSS LOSS")
        caption.setObjectName("lblGrossHeading")
        row.addWidget(caption)
        row.addStretch(1)
        self._profit_label = QLabel()
        self._profit_label.setObjectName("lblGrossProfit")
        self._paint(self._profit_label, Tone.POSITIVE)
        row.addWidget(self._profit_label)
        self._loss_label = QLabel()
        self._loss_label.setObjectName("lblGrossLoss")
        self._paint(self._loss_label, Tone.NEGATIVE)
        row.addWidget(self._loss_label)
        self.body_layout.addLayout(row)

        self._bar = QProgressBar()
        self._bar.setObjectName("grossProfitLossBar")
        self._bar.setRange(0, _BAR_SCALE)
        # The platform's own bar: the filled part is the profit share, and the
        # two figures above say which side is which. Its own number would read
        # as a percentage of nothing.
        self._bar.setTextVisible(False)
        self.body_layout.addWidget(self._bar)

        self._bar_caption = QLabel()
        self._bar_caption.setObjectName("lblBarCaption")
        self._bar_caption.setWordWrap(True)
        self.body_layout.addWidget(self._bar_caption)

    def _build_tree(self) -> None:
        self._tree = QTreeWidget()
        self._tree.setObjectName("metricsDetailTree")
        self._tree.setColumnCount(len(_COLUMNS))
        self._tree.setHeaderLabels(list(_COLUMNS))
        self._tree.setRootIsDecorated(False)
        # Sections are headings, not folders: nothing is collapsible, because a
        # collapsed section would hide numbers the user opened this to read.
        self._tree.setItemsExpandable(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self._tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header = self._tree.header()
        header.setSectionResizeMode(_METRIC_COLUMN, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            _VALUE_COLUMN, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            _VERDICT_COLUMN, QHeaderView.ResizeMode.ResizeToContents
        )
        self.body_layout.addWidget(self._tree, 1)

    def _build_footer(self) -> None:
        self._footer = QLabel()
        self._footer.setObjectName("lblMetricsFooter")
        self._footer.setWordWrap(True)
        self.body_layout.addWidget(self._footer)

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._btn_copy = QPushButton("Copy all")
        self._btn_copy.setObjectName("btnCopyMetrics")
        self._btn_copy.clicked.connect(self._on_copy)
        row.addWidget(self._btn_copy)
        row.addStretch(1)
        close = QPushButton("Close")
        close.setObjectName("btnCloseMetrics")
        close.clicked.connect(self.reject)
        row.addWidget(close)
        return row

    # -- host-facing -------------------------------------------------------

    def open_dialog(self) -> None:
        self.refresh()
        self.show()
        self.raise_()

    def refresh(self) -> None:
        """Re-reads the run's retained snapshot and redraws everything."""
        self._groups = build_groups(
            self._source.get_cards(),
            timeframe_seconds=self._source.get_timeframe_seconds(),
        )
        self._bar_data = build_gross_bar(
            gross_profit=self._source.get_gross_profit(),
            gross_loss=self._source.get_gross_loss(),
            profit_factor=self._source.get_profit_factor(),
        )
        self._footer_value = build_footer(
            total_closed_trades=self._source.get_total_closed_trades(),
            fee_rate_percent=self._source.get_fee_rate_percent(),
        )

        self._profit_label.setText(self._bar_data.profit_text)
        self._loss_label.setText(self._bar_data.loss_text)
        self._bar.setValue(round(self._bar_data.profit_share * _BAR_SCALE))
        self._bar_caption.setText(self._bar_data.caption)
        self._footer.setText(self._footer_value)
        self._fill_tree()

    def _fill_tree(self) -> None:
        self._tree.clear()
        for group in self._groups:
            heading = QTreeWidgetItem([group.label, "", ""])
            font = heading.font(_METRIC_COLUMN)
            font.setBold(True)
            heading.setFont(_METRIC_COLUMN, font)
            self._tree.addTopLevelItem(heading)
            heading.setExpanded(True)
            for row in group.rows:
                heading.addChild(self._row_item(row))

    def _row_item(self, row: MetricRow) -> QTreeWidgetItem:
        value = f"{row.value} {row.suffix}".strip()
        verdict = " ".join(part for part in (row.badge_text, row.info) if part)
        item = QTreeWidgetItem([row.title, value, verdict])
        item.setTextAlignment(
            _VALUE_COLUMN, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._colour_item(item, _VALUE_COLUMN, row.tone)
        self._colour_item(
            item, _VERDICT_COLUMN, row.badge_tone if row.badge_text else Tone.NEUTRAL
        )
        return item

    # -- rendering helpers -------------------------------------------------

    @staticmethod
    def _colour_item(item: QTreeWidgetItem, column: int, tone: Tone) -> None:
        colour = _tone_colour(tone)
        if colour is not None:
            item.setForeground(column, colour)

    @staticmethod
    def _paint(label: QLabel, tone: Tone) -> None:
        colour = _tone_colour(tone)
        if colour is None:
            return
        palette = label.palette()
        palette.setColor(label.foregroundRole(), colour)
        label.setPalette(palette)

    def _on_copy(self) -> None:
        if self._bar_data is None:  # pragma: no cover — refresh() runs in __init__
            return
        QGuiApplication.clipboard().setText(
            build_clipboard_text(self._groups, self._bar_data, self._footer_value)
        )
