"""`BOT-107A` — the "In-Sample vs Out-of-Sample" side-by-side metrics dialog.

Sourced entirely from the retained `BackTestViewModel.run_result
.comparison_snapshot()` (`ReportComparisonSnapshot.result.out_of_sample`) —
no file loading, no separate chart, unlike `ReportComparisonDialog`: both
halves come from the same run that is already on screen, and the chart's
own split is already drawn on the main chart via
`IBacktestChartHost.set_out_of_sample_divider()`. This dialog is only the
numeric side of the same feature.

Kept apart from `logic/out_of_sample_comparison_rules.py` (the pure
comparison math) per `architecture-rule.md` §5, same split every other
modal here uses (`metrics_detail_rules.py`/`metrics_detail_dialog.py`,
`report_comparison_rules.py`/`report_comparison_dialog.py`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.out_of_sample_validation import (
    OutOfSampleValidation,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.out_of_sample_comparison_rules import (
    build_out_of_sample_metric_rows,
    build_overfit_warning,
    build_split_description,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.report_comparison_rules import (
    MetricComparisonRow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    Overlay,
    Tone,
    semantic_colour,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_TITLE = "IN-SAMPLE VS OUT-OF-SAMPLE"
_METRIC_COLUMN = 0
_IN_SAMPLE_COLUMN = 1
_OUT_OF_SAMPLE_COLUMN = 2
_DELTA_COLUMN = 3
_COLUMNS = ("Metric", "In-Sample", "Out-of-Sample", "Δ (OOS − IS)")
_NO_DATA_TEXT = (
    "Out-of-sample validation was not computed for this run "
    "(too little data to split, or an older run)."
)


def _tone_colour(tone: Tone) -> QColor | None:
    if tone is Tone.POSITIVE:
        return QColor(semantic_colour("success"))
    if tone is Tone.NEGATIVE:
        return QColor(semantic_colour("danger"))
    return None


class OutOfSampleComparisonDialog(Overlay):
    """@brief Split description + overfit warning + metrics side-by-side
    table for the run currently on screen's `BOT-080` OOS validation."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        super().__init__(_TITLE, parent=parent)
        self.setObjectName("outOfSampleComparisonDialog")
        self.resize(660, 480)

        self._build_description_label()
        self._build_warning_label()
        self._build_metrics_tree()

        view_model.run_result.statCardsChanged.connect(self.refresh)
        self.refresh()

    # -- construction ------------------------------------------------------

    def _build_description_label(self) -> None:
        self._description_label = QLabel()
        self._description_label.setObjectName("lblOutOfSampleSplitDescription")
        self.body_layout.addWidget(self._description_label)

    def _build_warning_label(self) -> None:
        self._warning_label = QLabel()
        self._warning_label.setObjectName("lblOutOfSampleOverfitWarning")
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        self.body_layout.addWidget(self._warning_label)

    def _build_metrics_tree(self) -> None:
        self._tree = QTreeWidget()
        self._tree.setObjectName("outOfSampleMetricsTree")
        self._tree.setColumnCount(len(_COLUMNS))
        self._tree.setHeaderLabels(list(_COLUMNS))
        self._tree.setRootIsDecorated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        header = self._tree.header()
        header.setSectionResizeMode(_METRIC_COLUMN, QHeaderView.ResizeMode.Stretch)
        for column in (_IN_SAMPLE_COLUMN, _OUT_OF_SAMPLE_COLUMN, _DELTA_COLUMN):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.body_layout.addWidget(self._tree, 1)

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        close = QPushButton("Close")
        close.setObjectName("btnCloseOutOfSampleComparison")
        close.clicked.connect(self.reject)
        row.addWidget(close)
        return row

    # -- host-facing -------------------------------------------------------

    def open_dialog(self) -> None:
        self.refresh()
        self.show()
        self.raise_()

    def refresh(self) -> None:
        snapshot = self._vm.run_result.comparison_snapshot()
        validation = snapshot.result.out_of_sample if snapshot is not None else None
        self._render(validation)

    # -- rendering -----------------------------------------------------------

    def _render(self, validation: OutOfSampleValidation | None) -> None:
        if validation is None:
            self._description_label.setText(_NO_DATA_TEXT)
            self._warning_label.setVisible(False)
            self._tree.clear()
            return

        self._description_label.setText(build_split_description(validation))
        warning = build_overfit_warning(validation)
        self._warning_label.setText(warning)
        self._warning_label.setVisible(bool(warning))

        rows = build_out_of_sample_metric_rows(validation)
        self._fill_tree(rows)

    def _fill_tree(self, rows: list[MetricComparisonRow]) -> None:
        self._tree.clear()
        for row in rows:
            item = QTreeWidgetItem([row.label, row.value_a, row.value_b, row.delta])
            colour = _tone_colour(row.tone)
            if colour is not None:
                item.setForeground(_DELTA_COLUMN, colour)
            self._tree.addTopLevelItem(item)
