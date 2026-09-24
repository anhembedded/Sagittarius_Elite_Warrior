"""`BOT-115D` — the "compare 2 backtest reports side by side" modal.

Column A is always the result currently on screen (`BackTestViewModel
.run_result.comparison_snapshot()`, retained by `BackTestPresenter` right
alongside its stat cards — see `ReportComparisonSnapshot`'s own docstring).
Column B is always loaded from a `.sagi-report.json`/`.gz` file picked from
this dialog. Task §2.4 allows either column to be "a file on disk or the
result on screen"; this dialog covers the single most common real use of
that ("what's on screen right now, against a saved baseline") without a
second source-picker UI for column A — column A already IS whatever is on
screen, which is the point of comparing.

Kept apart from `logic/report_comparison_rules.py` (the pure comparison
math) per `architecture-rule.md` §5, same split every other modal here
uses (`metrics_detail_rules.py`/`metrics_detail_dialog.py`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_report_loader import (
    load_backtest_report,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui._report_comparison_chart_widget import (
    ReportComparisonChartWidget,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.report_comparison_rules import (
    MetricComparisonRow,
    build_config_diff_text,
    build_equity_comparison_series,
    build_loaded_file_label,
    build_market_mismatch_warning,
    build_metric_comparison_rows,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.report_comparison_snapshot import (
    ReportComparisonSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.report_import import (
    backtest_report_to_run_config,
    read_backtest_report_bytes,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    Overlay,
    Tone,
    semantic_colour,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_TITLE = "COMPARE BACKTEST REPORTS"
_LOAD_DIALOG_TITLE = "Load report to compare"
_REPORT_FILE_FILTER = "Backtest report (*.sagi-report.json *.sagi-report.json.gz)"
_METRIC_COLUMN = 0
_A_COLUMN = 1
_B_COLUMN = 2
_DELTA_COLUMN = 3
_COLUMNS = ("Metric", "Column A", "Column B", "Δ (B − A)")
_NO_COLUMN_A_TEXT = "Run a backtest first to fill Column A."
_NO_COLUMN_B_TEXT = "Load a report to fill Column B."


def _tone_colour(tone: Tone) -> QColor | None:
    if tone is Tone.POSITIVE:
        return QColor(semantic_colour("success"))
    if tone is Tone.NEGATIVE:
        return QColor(semantic_colour("danger"))
    return None


class ReportComparisonDialog(Overlay):
    """@brief Config-diff line + metrics side-by-side table + overlaid
    equity curves for the report currently on screen (Column A) against a
    report loaded from disk (Column B)."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        self._loaded_b: ReportComparisonSnapshot | None = None
        self._loaded_b_label = ""
        self._load_error = ""
        super().__init__(_TITLE, parent=parent)
        self.setObjectName("reportComparisonDialog")
        self.resize(780, 680)

        self._build_column_labels()
        self._build_diff_and_warning_labels()
        self._build_metrics_tree()
        self._build_chart()

        view_model.run_result.statCardsChanged.connect(self.refresh)
        self.refresh()

    # -- construction ------------------------------------------------------

    def _build_column_labels(self) -> None:
        row = QHBoxLayout()
        self._column_a_label = QLabel()
        self._column_a_label.setObjectName("lblComparisonColumnA")
        row.addWidget(self._column_a_label, 1)

        self._column_b_label = QLabel()
        self._column_b_label.setObjectName("lblComparisonColumnB")
        row.addWidget(self._column_b_label, 1)

        self._btn_load_b = QPushButton("Load report to compare…")
        self._btn_load_b.setObjectName("btnLoadComparisonReport")
        self._btn_load_b.clicked.connect(self._on_load_column_b)
        row.addWidget(self._btn_load_b)
        self.body_layout.addLayout(row)

    def _build_diff_and_warning_labels(self) -> None:
        self._diff_label = QLabel()
        self._diff_label.setObjectName("lblComparisonConfigDiff")
        self._diff_label.setWordWrap(True)
        self.body_layout.addWidget(self._diff_label)

        self._warning_label = QLabel()
        self._warning_label.setObjectName("lblComparisonWarning")
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        self.body_layout.addWidget(self._warning_label)

    def _build_metrics_tree(self) -> None:
        self._tree = QTreeWidget()
        self._tree.setObjectName("comparisonMetricsTree")
        self._tree.setColumnCount(len(_COLUMNS))
        self._tree.setHeaderLabels(list(_COLUMNS))
        self._tree.setRootIsDecorated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        header = self._tree.header()
        header.setSectionResizeMode(_METRIC_COLUMN, QHeaderView.ResizeMode.Stretch)
        for column in (_A_COLUMN, _B_COLUMN, _DELTA_COLUMN):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.body_layout.addWidget(self._tree, 1)

    def _build_chart(self) -> None:
        self._chart = ReportComparisonChartWidget()
        self.body_layout.addWidget(self._chart, 1)

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        close = QPushButton("Close")
        close.setObjectName("btnCloseComparison")
        close.clicked.connect(self.reject)
        row.addWidget(close)
        return row

    # -- host-facing -------------------------------------------------------

    def open_dialog(self) -> None:
        self.refresh()
        self.show()
        self.raise_()

    def refresh(self) -> None:
        """Re-reads Column A's retained snapshot and redraws everything —
        Column B stays whatever the user last loaded until they load a
        different file."""
        snapshot_a = self._vm.run_result.comparison_snapshot()
        self._render(snapshot_a, self._loaded_b)

    # -- loading column B ----------------------------------------------------

    def _on_load_column_b(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, _LOAD_DIALOG_TITLE, "", _REPORT_FILE_FILTER
        )
        if not path:
            return
        try:
            data = read_backtest_report_bytes(path)
        except OSError as exc:
            self._load_error = f"Could not read file: {exc}"
            self._loaded_b = None
            self._loaded_b_label = ""
            self.refresh()
            return
        loaded = load_backtest_report(data, valid_strategy_keys=set())
        if loaded.report is None:
            self._load_error = (
                loaded.error.message
                if loaded.error is not None
                else "Could not load report."
            )
            self._loaded_b = None
            self._loaded_b_label = ""
            self.refresh()
            return
        run_config = backtest_report_to_run_config(loaded.report)
        self._loaded_b = ReportComparisonSnapshot(run_config, loaded.report.result)
        self._loaded_b_label = build_loaded_file_label(path)
        self._load_error = ""
        self.refresh()

    # -- rendering -----------------------------------------------------------

    def _render(
        self,
        snapshot_a: ReportComparisonSnapshot | None,
        snapshot_b: ReportComparisonSnapshot | None,
    ) -> None:
        self._column_a_label.setText(
            f"Column A — {snapshot_a.run_config.to_summary_label()}"
            if snapshot_a is not None
            else f"Column A — {_NO_COLUMN_A_TEXT}"
        )
        self._column_b_label.setText(
            f"Column B — {self._loaded_b_label}"
            if snapshot_b is not None
            else f"Column B — {self._load_error or _NO_COLUMN_B_TEXT}"
        )

        if snapshot_a is None or snapshot_b is None:
            self._diff_label.setText("")
            self._warning_label.setVisible(False)
            self._tree.clear()
            self._chart.set_series([], [])
            return

        self._diff_label.setText(
            build_config_diff_text(snapshot_a.run_config, snapshot_b.run_config)
        )
        warning = build_market_mismatch_warning(
            snapshot_a.run_config, snapshot_b.run_config
        )
        self._warning_label.setText(warning)
        self._warning_label.setVisible(bool(warning))

        rows = build_metric_comparison_rows(
            snapshot_a.result.metrics, snapshot_b.result.metrics
        )
        self._fill_tree(rows)

        points_a, points_b = build_equity_comparison_series(
            snapshot_a.result.equity_curve,
            snapshot_a.result.initial_balance,
            snapshot_b.result.equity_curve,
            snapshot_b.result.initial_balance,
        )
        self._chart.set_series(points_a, points_b)

    def _fill_tree(self, rows: list[MetricComparisonRow]) -> None:
        self._tree.clear()
        for row in rows:
            item = QTreeWidgetItem([row.label, row.value_a, row.value_b, row.delta])
            colour = _tone_colour(row.tone)
            if colour is not None:
                item.setForeground(_DELTA_COLUMN, colour)
            self._tree.addTopLevelItem(item)
