"""Backtest extended-metrics readout — a dialog with a table in it.

## Three renderings, and what each one answered

`ExtendedMetricsDialog` drew it as a `StatGrid` of cards. `EPIC-015` Phase 3
replaced that with `MetricsDetailPanel.qml` + `MetricsDetailVM` behind a
hand-written modal host, because the design wanted sections, verdict badges and
a profit-against-loss bar that the grid could not express. `EPIC-025` PR 4.3j
keeps every one of those and deletes the `.qml`: HLD §11.3 maps a readout like
this to *a dialog with a table*. It was a `QTreeWidget`, the platform's
answer to "rows under headings"; since `EPIC-033L` stage 5 it is a
`SpecTable` built from column specs (`metrics_detail_model.py`), the section
its first column. It stays a table now that the Engine configures grouped
trees too (`BOT-151`): its values are text in mixed units, which a tree would
sort as text, and the table sorts them back to the read-out's own order.

Three things the QML version needed and this does not: a `QQuickWidget` host
supplying modality that `kit/DialogShell.qml` had no way to provide, a
`QObject` re-publishing every value for bindings to read, and a
`Theme` install so the scene could colour itself. `QDialog` is modal, the rules
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

from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.metrics_detail_rules import (
    GrossBar,
    MetricGroup,
    build_clipboard_text,
    build_footer,
    build_gross_bar,
    build_groups,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)

from ..metrics_detail_model import detail_rows, metrics_detail_table
from .backtest_metrics_detail_source import BacktestMetricsDetailSource

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_TITLE = "Metrics Detail"
_NO_METRICS_TEXT = "Run a backtest to see its metrics."

#: The bar is drawn in permille rather than percent so a share of, say, 3.7%
#: does not collapse to 4 — the caption under it quotes two decimals.
_BAR_SCALE = 1000


class MetricsDetailDialogWidget(QDialog):
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
        super().__init__(parent)
        self._vm = view_model
        self._source = BacktestMetricsDetailSource(view_model)
        self._groups: tuple[MetricGroup, ...] = ()
        self._bar_data: GrossBar | None = None
        self._footer_value = ""
        self.setWindowTitle(_TITLE)
        self.body_layout = QVBoxLayout(self)
        self.setObjectName("backtestMetricsDetailDialog")
        self.resize(660, 700)

        self._build_bar_row()
        self._build_tree()
        self._build_footer()

        self.body_layout.addWidget(self._build_buttons())

        view_model.run_result.statCardsChanged.connect(self.refresh)
        self.refresh()

    # -- construction ------------------------------------------------------

    def _build_bar_row(self) -> None:
        row = QHBoxLayout()
        caption = QLabel("Gross profit vs gross loss")
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
        # A table with the section as its first column since `EPIC-033L`
        # stage 5 (`metrics_detail_model.py`); see the module docstring for
        # why it is not a grouped tree.
        self._table = metrics_detail_table(_NO_METRICS_TEXT)
        self.body_layout.addWidget(self._table.body, 1)

    def _build_footer(self) -> None:
        self._footer = QLabel()
        self._footer.setObjectName("lblMetricsFooter")
        self._footer.setWordWrap(True)
        self.body_layout.addWidget(self._footer)

    def _build_buttons(self) -> QDialogButtonBox:
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setObjectName(
            "btnCloseMetrics"
        )
        self._btn_copy = buttons.addButton(
            "&Copy all", QDialogButtonBox.ButtonRole.ActionRole
        )
        self._btn_copy.setObjectName("btnCopyMetrics")
        self._btn_copy.clicked.connect(self._on_copy)
        buttons.rejected.connect(self.reject)
        return buttons

    # -- host-facing -------------------------------------------------------

    def open_dialog(self) -> None:
        self.refresh()
        self.open()

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
        self._table.model.set_rows(detail_rows(self._groups))

    # -- rendering helpers -------------------------------------------------

    @staticmethod
    def _paint(label: QLabel, tone: Tone) -> None:
        colour = tone_colour(tone)
        if colour is None:
            return
        palette = QPalette(label.palette())
        palette.setColor(QPalette.ColorRole.WindowText, colour)
        label.setPalette(palette)

    def _on_copy(self) -> None:
        if self._bar_data is None:  # pragma: no cover — refresh() runs in __init__
            return
        QGuiApplication.clipboard().setText(
            build_clipboard_text(self._groups, self._bar_data, self._footer_value)
        )
