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

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
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
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

from ..metric_comparison_model import OutOfSampleComparisonModel, comparison_table

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_TITLE = "In-Sample vs Out-of-Sample"
_NO_DATA_TEXT = (
    "Out-of-sample validation was not computed for this run "
    "(too little data to split, or an older run)."
)

#: The empty table's text (review of PR #364): short, and true whichever
#: side is missing.
_NO_FIGURES_TEXT = "No out-of-sample figures."


class OutOfSampleComparisonDialog(QDialog):
    """@brief Split description + overfit warning + metrics side-by-side
    table for the run currently on screen's `BOT-080` OOS validation."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setWindowTitle(_TITLE)
        self.body_layout = QVBoxLayout(self)
        self.setObjectName("outOfSampleComparisonDialog")
        self.resize(660, 480)

        self._build_description_label()
        self._build_warning_label()
        self._build_metrics_tree()

        self.body_layout.addWidget(self._build_buttons())

        view_model.run_result.statCardsChanged.connect(self.refresh)
        self.refresh()

    # -- construction ------------------------------------------------------

    def _build_description_label(self) -> None:
        self._description_label = plain_label()
        self._description_label.setObjectName("lblOutOfSampleSplitDescription")
        self.body_layout.addWidget(self._description_label)

    def _build_warning_label(self) -> None:
        self._warning_label = plain_label()
        self._warning_label.setObjectName("lblOutOfSampleOverfitWarning")
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        self.body_layout.addWidget(self._warning_label)

    def _build_metrics_tree(self) -> None:
        self._table = comparison_table(
            OutOfSampleComparisonModel(self), "outOfSampleMetricsTree", _NO_FIGURES_TEXT
        )
        self.body_layout.addWidget(self._table.body, 1)

    def _build_buttons(self) -> QDialogButtonBox:
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setObjectName(
            "btnCloseOutOfSampleComparison"
        )
        buttons.rejected.connect(self.reject)
        return buttons

    # -- host-facing -------------------------------------------------------

    def open_dialog(self) -> None:
        self.refresh()
        self.open()

    def refresh(self) -> None:
        snapshot = self._vm.run_result.comparison_snapshot()
        validation = snapshot.result.out_of_sample if snapshot is not None else None
        self._render(validation)

    # -- rendering -----------------------------------------------------------

    def _render(self, validation: OutOfSampleValidation | None) -> None:
        if validation is None:
            self._description_label.setText(_NO_DATA_TEXT)
            self._warning_label.setVisible(False)
            self._table.model.clear()
            return

        self._description_label.setText(build_split_description(validation))
        warning = build_overfit_warning(validation)
        self._warning_label.setText(warning)
        self._warning_label.setVisible(bool(warning))

        rows = build_out_of_sample_metric_rows(validation)
        self._table.model.set_rows(rows)
