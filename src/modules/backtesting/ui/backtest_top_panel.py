"""The Backtest mode's Metrics dock (`EPIC-033L`, HLD §11.2.1: "right:
Metrics"): the notices about the run on screen, and its figures.

Since `EPIC-033L` stage 4 it is stock controls in the dock's own layout: the
notices are `NoticeBar`s, the figures `BacktestStatRow`, the message of a
run that produced none a read-only `QPlainTextEdit`. It replaces a card
painted on the app background inside the dock, with a second heading (an
accent bar and "BACKTEST PERFORMANCE METRICS" above the dock's own title),
pill buttons and a monospaced result box, each with its style sheet.

The toolbar of pickers that once sat on top of it is the Run setup dock
(`run_setup_panel.py`); the run's progress banner is the status bar's
(`run_progress_status.py`), stopped by Tools → Stop backtest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .backtest_stat_row import BacktestStatRow
from .notice_bar import NoticeBar, NoticeKind

if TYPE_CHECKING:
    from .backtest_view_model import BackTestViewModel


#: `BOT-095G` — always index 0, never a real run; `itemData(0)` is `""`,
#: which `_on_run_history_selected` reads as "nothing to restore".
_RUN_HISTORY_PLACEHOLDER = "Previous runs…"
_PREVIEW_TEXT = (
    "Preview chart: no backtest has run yet. Run one with Tools → Run backtest (F7)."
)


class BackTestTopPanel(QWidget):  # base-exempt: a dock's content, not a surface
    """The Metrics dock's content."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._vm = view_model

        self._preview_banner = NoticeBar(
            NoticeKind.INFORMATION, "backtestChartPreviewBanner"
        )
        self._preview_banner.text = _PREVIEW_TEXT
        self._stale_banner = NoticeBar(
            NoticeKind.WARNING, "backtestStaleWarningBanner", "Run now"
        )
        self._stale_banner.action_button.clicked.connect(self._vm.requestRun)
        self._coverage_banner = NoticeBar(
            NoticeKind.WARNING, "backtestCoverageWarningBanner"
        )
        # `BOT-115C` — names the imported file and offers a way back to a
        # clean slate without running or editing anything.
        self._imported_report_banner = NoticeBar(
            NoticeKind.INFORMATION, "backtestImportedReportBanner", "Exit view"
        )
        self._imported_report_banner.action_button.clicked.connect(
            self._vm.requestExitImportedReportView
        )
        self._metrics_header = self._build_metrics_header()
        # `EPIC-025` PR 4.3g: read-only tiles (HLD §11.3). The row reads
        # `primaryStatCards` through its callback; `_sync_stat_cards()` only
        # says *when* to re-pull it.
        self._stat_cards_row = BacktestStatRow(
            lambda: self._vm.run_result.primaryStatCards
        )
        self._result_warning_label = QLabel()
        self._result_warning_label.setObjectName("lblResultWarning")
        self._result_warning_label.setWordWrap(True)
        self._result_box = self._build_result_box()

        layout = QVBoxLayout(self)
        for widget in (
            self._preview_banner,
            self._stale_banner,
            self._coverage_banner,
            self._imported_report_banner,
            self._metrics_header,
            self._stat_cards_row,
            self._result_warning_label,
            self._result_box,
        ):
            layout.addWidget(widget)
        layout.addStretch(1)

        self._wire_view_model()
        self._sync_all()

    def _build_metrics_header(self) -> QWidget:
        """Details, Limitations and the run history, on one row under the
        dock's title."""
        header = QWidget()
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        # Opens a window that only shows more: no ellipsis (MS `cmd-menus`).
        self._btn_expand_metrics = QPushButton("Details")
        self._btn_expand_metrics.setObjectName("lnkExpandMetrics")
        self._btn_expand_metrics.setToolTip("Every figure of this run, by section")
        self._btn_expand_metrics.clicked.connect(self._vm.requestOpenExtendedMetrics)
        row.addWidget(self._btn_expand_metrics)
        self._btn_limitations = QPushButton("Limitations")
        self._btn_limitations.setObjectName("btnBacktestLimitations")
        self._btn_limitations.setToolTip("What this run's simulation leaves out")
        self._btn_limitations.clicked.connect(self._vm.requestOpenLimitations)
        row.addWidget(self._btn_limitations)
        self._combo_run_history = QComboBox()
        self._combo_run_history.setObjectName("comboSessionRunHistory")
        self._combo_run_history.setToolTip(
            "Redisplay an earlier run from this session, without re-running it"
        )
        self._combo_run_history.addItem(_RUN_HISTORY_PLACEHOLDER, "")
        self._combo_run_history.setEnabled(False)
        self._combo_run_history.currentIndexChanged.connect(
            self._on_run_history_selected
        )
        row.addWidget(self._combo_run_history, 1)
        return header

    def _build_result_box(self) -> QWidget:
        """What a run that produced no figures said, and a way to fetch the
        candles it lacked."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        # A failed run or sync says so with the platform's error icon as
        # well as its words; red text alone was the only signal before.
        self._result_error = NoticeBar(NoticeKind.CRITICAL, "backtestResultError")
        layout.addWidget(self._result_error)
        self._result_text = QPlainTextEdit()
        self._result_text.setObjectName("txtBacktestResult")
        self._result_text.setReadOnly(True)
        layout.addWidget(self._result_text)
        self._btn_request_sync = QPushButton()
        self._btn_request_sync.setObjectName("btnRequestSync")
        self._btn_request_sync.clicked.connect(self._vm.requestSync)
        row = QHBoxLayout()
        row.addWidget(self._btn_request_sync)
        row.addStretch(1)
        layout.addLayout(row)
        return widget

    # ------------------------------------------------------------------ #
    # ViewModel wiring
    # ------------------------------------------------------------------ #

    def _wire_view_model(self) -> None:
        vm = self._vm
        vm.controlsEnabledChanged.connect(self._sync_controls_enabled)
        vm.uiModeChanged.connect(self._sync_controls_enabled)
        vm.isConfigDirtyChanged.connect(self._sync_banners)
        vm.uiModeChanged.connect(self._sync_banners)
        vm.isChartPreviewChanged.connect(self._sync_banners)
        vm.run_result.dataCoverageChanged.connect(self._sync_banners)
        vm.run_result.needsDataSyncChanged.connect(self._sync_banners)
        vm.configDiffSummaryChanged.connect(self._sync_banners)
        vm.importedReportBannerTextChanged.connect(self._sync_banners)
        vm.run_result.statCardsChanged.connect(self._sync_stat_cards)
        vm.run_result.statCardsChanged.connect(self._sync_metrics_header)
        vm.run_result.resultWarningTextChanged.connect(self._sync_metrics_header)
        vm.run_result.resultChanged.connect(self._sync_result_box)
        vm.run_result.needsDataSyncChanged.connect(self._sync_result_box)
        vm.sessionRunHistoryChanged.connect(self._sync_session_run_history)

    def _sync_all(self) -> None:
        self._sync_controls_enabled()
        self._sync_banners()
        self._sync_stat_cards()
        self._sync_metrics_header()
        self._sync_result_box()
        self._sync_session_run_history()

    def _sync_controls_enabled(self) -> None:
        # `BOT-095G` — a busy run/sync owns the screen the same way it owns
        # the Run setup (`run_setup_panel.py`); `and` rather than an outright
        # `setEnabled(enabled)` so an empty history still shows disabled
        # once a run finishes, instead of springing back on with only the
        # placeholder to pick.
        enabled = bool(self._vm.controlsEnabled)
        self._combo_run_history.setEnabled(
            enabled and self._combo_run_history.count() > 1
        )

    def _sync_banners(self) -> None:
        vm = self._vm
        mode = vm.uiMode
        self._preview_banner.setVisible(bool(vm.isChartPreview))

        self._stale_banner.setVisible(bool(vm.isConfigDirty))
        if vm.isConfigDirty:
            self._stale_banner.text = (
                f"Configuration changed ({vm.configDiffSummary}). "
                f"The results below have not been updated."
            )

        coverage_visible = (
            bool(vm.run_result.needsDataSync)
            and vm.run_result.dataCoverageMessage != ""
        )
        self._coverage_banner.setVisible(coverage_visible)
        if coverage_visible:
            self._coverage_banner.text = vm.run_result.dataCoverageMessage

        imported_report_visible = mode == "VIEWING_IMPORTED_REPORT" and bool(
            vm.importedReportBannerText
        )
        self._imported_report_banner.setVisible(imported_report_visible)
        if imported_report_visible:
            self._imported_report_banner.text = vm.importedReportBannerText

    def _sync_stat_cards(self) -> None:
        has_cards = bool(self._vm.run_result.primaryStatCards)
        self._stat_cards_row.setVisible(has_cards)
        self._result_box.setVisible(not has_cards)
        if has_cards:
            # The row reads `primaryStatCards` through its own callback, so
            # this says *when*, never what: one call per `statCardsChanged`.
            self._stat_cards_row.refresh()

    def _sync_metrics_header(self) -> None:
        has_cards = bool(self._vm.run_result.primaryStatCards)
        self._metrics_header.setVisible(has_cards)
        text = self._vm.run_result.resultWarningText
        self._result_warning_label.setText(text)
        self._result_warning_label.setVisible(has_cards and bool(text))

    def _sync_session_run_history(self) -> None:
        """`BOT-095G` — repopulates the dropdown from
        `vm.sessionRunHistory`, always resetting the selection to the
        placeholder: after a push (a new run finished) or an eviction (the
        oldest slot fell off `MAX_HISTORY`), whatever was previously picked
        no longer represents "the current on-screen run" — leaving an old
        selection highlighted would be misleading in either case."""
        combo = self._combo_run_history
        entries = self._vm.sessionRunHistory
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItem(_RUN_HISTORY_PLACEHOLDER, "")
            for entry in entries:
                combo.addItem(entry["label"], entry["run_id"])
            combo.setCurrentIndex(0)
        finally:
            combo.blockSignals(False)
        # `controlsEnabled` (a busy run/sync) still wins even with entries
        # present — `_sync_controls_enabled` is the one place that combines
        # both conditions.
        self._sync_controls_enabled()

    def _on_run_history_selected(self, index: int) -> None:
        run_id = self._combo_run_history.itemData(index)
        if run_id:
            self._vm.requestRestoreRun(run_id)

    def _sync_result_box(self) -> None:
        vm = self._vm
        failed = bool(vm.run_result.resultIsError)
        self._result_error.text = vm.run_result.resultText if failed else ""
        self._result_error.setVisible(failed)
        self._result_text.setPlainText("" if failed else vm.run_result.resultText)
        self._result_text.setVisible(not failed)
        syncing = vm.uiMode == "SYNCING"
        self._btn_request_sync.setVisible(bool(vm.run_result.needsDataSync))
        self._btn_request_sync.setEnabled(not syncing)
        self._btn_request_sync.setText("Syncing…" if syncing else "Sync data now")
