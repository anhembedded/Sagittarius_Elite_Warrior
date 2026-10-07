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

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_report_loader import (
    load_backtest_report,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui._report_comparison_chart_widget import (
    ReportComparisonChartWidget,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.report_comparison_rules import (
    build_config_diff_text,
    build_equity_comparison_series,
    build_loaded_file_label,
    build_market_mismatch_warning,
    build_market_type_mismatch_warning,
    build_metric_comparison_rows,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.report_comparison_snapshot import (
    ReportComparisonSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.report_import import (
    backtest_report_to_run_config,
    read_backtest_report_bytes,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

from ..metric_comparison_model import ReportComparisonModel, comparison_table

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_TITLE = "Compare Reports"
_LOAD_DIALOG_TITLE = "Load report to compare"
_REPORT_FILE_FILTER = "Backtest report (*.sagi-report.json *.sagi-report.json.gz)"
_NO_COLUMN_A_TEXT = "Run a backtest first to fill Column A."
_NO_COLUMN_B_TEXT = "Load a report to fill Column B."

#: The empty table's text (review of PR #364): short, and true whichever
#: side is missing.
_NOTHING_TO_COMPARE_TEXT = "Both columns need a run or a report to compare."


class ReportComparisonDialog(QDialog):
    """@brief Config-diff line + metrics side-by-side table + overlaid
    equity curves for the report currently on screen (Column A) against a
    report loaded from disk (Column B)."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._loaded_b: ReportComparisonSnapshot | None = None
        self._loaded_b_label = ""
        self._load_error = ""
        self.setWindowTitle(_TITLE)
        self.body_layout = QVBoxLayout(self)
        self.setObjectName("reportComparisonDialog")
        self.resize(780, 680)

        self._build_column_labels()
        self._build_diff_and_warning_labels()
        self._build_metrics_tree()
        self._build_chart()

        self.body_layout.addWidget(self._build_buttons())

        view_model.run_result.statCardsChanged.connect(self.refresh)
        self.refresh()

    # -- construction ------------------------------------------------------

    def _build_column_labels(self) -> None:
        row = QHBoxLayout()
        self._column_a_label = plain_label()
        self._column_a_label.setObjectName("lblComparisonColumnA")
        row.addWidget(self._column_a_label, 1)

        self._column_b_label = plain_label()
        self._column_b_label.setObjectName("lblComparisonColumnB")
        row.addWidget(self._column_b_label, 1)

        self._btn_load_b = QPushButton("Load report to compare…")
        self._btn_load_b.setObjectName("btnLoadComparisonReport")
        self._btn_load_b.clicked.connect(self._on_load_column_b)
        row.addWidget(self._btn_load_b)
        self.body_layout.addLayout(row)

    def _build_diff_and_warning_labels(self) -> None:
        self._diff_label = plain_label()
        self._diff_label.setObjectName("lblComparisonConfigDiff")
        self._diff_label.setWordWrap(True)
        self.body_layout.addWidget(self._diff_label)

        self._warning_label = plain_label()
        self._warning_label.setObjectName("lblComparisonWarning")
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        self.body_layout.addWidget(self._warning_label)

    def _build_metrics_tree(self) -> None:
        self._table = comparison_table(
            ReportComparisonModel(self),
            "comparisonMetricsTree",
            _NOTHING_TO_COMPARE_TEXT,
        )
        self.body_layout.addWidget(self._table.body, 1)

    def _build_chart(self) -> None:
        self._chart = ReportComparisonChartWidget()
        self.body_layout.addWidget(self._chart, 1)

    def _build_buttons(self) -> QDialogButtonBox:
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setObjectName(
            "btnCloseComparison"
        )
        buttons.rejected.connect(self.reject)
        return buttons

    # -- host-facing -------------------------------------------------------

    def open_dialog(self) -> None:
        self.refresh()
        self.open()

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
            self._table.model.clear()
            self._chart.set_series([], [])
            return

        self._diff_label.setText(
            build_config_diff_text(snapshot_a.run_config, snapshot_b.run_config)
        )
        warning = "   •   ".join(
            note
            for note in (
                build_market_mismatch_warning(
                    snapshot_a.run_config, snapshot_b.run_config
                ),
                build_market_type_mismatch_warning(
                    snapshot_a.run_config, snapshot_b.run_config
                ),
            )
            if note
        )
        self._warning_label.setText(warning)
        self._warning_label.setVisible(bool(warning))

        rows = build_metric_comparison_rows(
            snapshot_a.result.metrics, snapshot_b.result.metrics
        )
        self._table.model.set_rows(rows)

        points_a, points_b = build_equity_comparison_series(
            snapshot_a.result, snapshot_b.result
        )
        self._chart.set_series(points_a, points_b)
