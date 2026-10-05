"""EPIC-006E: `BackTestTopPanel.qml` -> QtWidgets.

Progress/preview/stale/coverage banners and the performance figures: since
`EPIC-033L` the content of the Backtest mode's Metrics dock. The toolbar of
pickers that once sat on top of it is the Run setup dock
(`run_setup_panel.py`). Every `objectName` from the QML port carries over
unchanged (tests/presenter both key off them).

`EPIC-015` Phase 4 replaced two pieces of that QtWidgets port with QML
embeds: `ProgressBannerWidget` (`qml/kit/`) for the run/sync progress banner,
and `StatCardRowWidget` (`qml/StatCardRow/`) for the performance figures.
`EPIC-025` PR 4.3g took the second one back and PR 4.3l the first (ADR D21):
the figures are `BacktestStatRow` and the banner is `kit.ProgressBanner`, both
QtWidgets, so `cardMetric_N` and the Cancel button are `QWidget`s reachable by
`findChild` rather than through a QML scene. `backtestProgressBanner` (the
outer `QFrame`) and the four `_sync_*`/`_build_*` method names are unchanged
throughout.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import (
    CANCELLING_CAPTION,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    Banner,
    ProgressBanner,
    Severity,
    StyleRole,
    apply_role,
)

from .backtest_stat_row import BacktestStatRow

if TYPE_CHECKING:
    from .backtest_view_model import BackTestViewModel


def _clamp_percent(value: float) -> float:
    """@brief `BackTestViewModel.backtestProgressPercent`/`syncProgressPercent`
    to the 0..100 range `kit.ProgressBanner` expects.

    @details Unlike `DataManagementViewModel.progressPercent` (clamped at
    the property getter itself), these two properties store whatever
    `set_backtest_progress()`/`set_sync_progress()` were last called with,
    with no clamp of their own. Every real caller today already clamps
    before calling (`backtest_presenter.py`'s
    `_on_backtest_progress_for_action`/`_on_sync_progress_for_action` both
    do `min(100.0, max(0.0, ...))`), so this is a defensive backstop, not a
    fix for an observed bug. `ProgressBanner` clamps in `set_percent()` as
    well, since PR 4.3l — the `.qml` this replaced clamped its bar *width*
    (`Math.max(0, Math.min(1, root.percent / 100))`) but not its percent
    *text* (`Math.round(root.percent) + "%"`), so an unclamped value showed
    "150%" beside a visually full bar. Kept here rather than deleted as
    now-redundant: this is the panel saying what it will send, and the widget
    defending itself is not the same promise.
    """
    return min(100.0, max(0.0, value))


#: `BOT-095G` — always index 0, never a real run; `itemData(0)` is `""`,
#: which `_on_run_history_selected` reads as "nothing to restore".
_RUN_HISTORY_PLACEHOLDER = "Previous runs…"


class BackTestTopPanel(QWidget):  # base-exempt: screen region on app bg
    """Port of `BackTestTopPanel.qml`. Sizes itself naturally via its own
    layout (no `implicitHeight` read-back hack needed — that only existed
    to work around `QQuickWidget`'s `SizeRootObjectToView` ignoring QML's
    `implicitHeight`; a plain `QWidget`'s `sizeHint()` already reflects
    what its layout needs).

    **Deliberately not a `Surface`**, unlike the cards it contains. It
    paints the app background and draws no border of its own — it is the
    strip the cards and banners sit *on*, not one of them. Same call as
    `DevBoardPanel` (`EPIC-007F`)."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        # Scoped, not a bare property list: unscoped this repaints every
        # descendant that has no rule of its own (`BUG-008`), which here is
        # most of the toolbar.
        self.setStyleSheet(
            f"{type(self).__name__} {{ background-color: {Palette.BG}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        self._card = QFrame()
        apply_role(self._card, StyleRole.SURFACE)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(8)
        outer.addWidget(self._card)

        self._progress_banner = self._build_progress_banner()
        card_layout.addWidget(self._progress_banner)
        self._preview_banner = self._build_preview_banner()
        card_layout.addWidget(self._preview_banner)
        self._stale_banner = self._build_stale_banner()
        card_layout.addWidget(self._stale_banner)
        self._coverage_banner = self._build_coverage_banner()
        card_layout.addWidget(self._coverage_banner)
        self._imported_report_banner = self._build_imported_report_banner()
        card_layout.addWidget(self._imported_report_banner)
        card_layout.addWidget(self._build_metrics_header())

        self._stat_cards_row = self._build_stat_cards_row()
        card_layout.addWidget(self._stat_cards_row)
        self._result_warning_label = self._build_result_warning_label()
        card_layout.addWidget(self._result_warning_label)
        self._result_box = self._build_result_box()
        card_layout.addWidget(self._result_box)

        self._wire_view_model()
        self._sync_all()

    # ------------------------------------------------------------------ #
    # Banners
    # ------------------------------------------------------------------ #

    def _build_progress_banner(self) -> QFrame:
        banner = QFrame()
        banner.setObjectName("backtestProgressBanner")
        # PR 4.3l's `kit.ProgressBanner` in a bordered `QFrame`: unlike Data
        # Management's, this banner sits inside the SURFACE-styled card, so
        # it needs its own background/border to read as a distinct strip.
        banner.setStyleSheet(
            f"QFrame {{ background-color: {Palette.BG_CARD}; "
            f"border: 1px solid {Palette.STATE_NAV_BORDER}; border-radius: 6px; }}"
        )
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(12, 4, 12, 4)
        self._progress_banner_widget = ProgressBanner()
        self._progress_banner_widget.cancelRequested.connect(
            self._vm.requestCancelBacktest
        )
        layout.addWidget(self._progress_banner_widget, 1)
        banner.setVisible(False)
        return banner

    def _build_preview_banner(self) -> Banner:
        banner = Banner(
            'Preview chart — backtest not run yet. Click "RUN BACKTEST" to see '
            "actual results.",
            severity=Severity.INFO,
        )
        banner.setObjectName("backtestChartPreviewBanner")
        # `Banner` takes its icon as a `str` because it has no icon loader to
        # depend on; this app does, so it sets the pixmap on the slot the
        # class leaves public for exactly this.
        self._set_banner_icon(banner, "info", Palette.ACCENT)
        banner.setVisible(False)
        return self._tighten(banner)

    def _build_stale_banner(self) -> Banner:
        banner = Banner(severity=Severity.WARN, action_text="Run now")
        banner.setObjectName("backtestStaleWarningBanner")
        self._set_banner_icon(banner, "triangle-alert", Palette.WARNING)
        banner.action_button.clicked.connect(self._vm.requestRun)
        banner.setVisible(False)
        return self._tighten(banner)

    def _build_coverage_banner(self) -> Banner:
        banner = Banner(severity=Severity.WARN)
        banner.setObjectName("backtestCoverageWarningBanner")
        banner.setVisible(False)
        return self._tighten(banner)

    def _build_imported_report_banner(self) -> Banner:
        """`BOT-115C` — visible only in `VIEWING_IMPORTED_REPORT`, naming
        the source file and offering a way back to a clean slate without
        running or editing anything."""
        banner = Banner(severity=Severity.INFO, action_text="Exit view")
        banner.setObjectName("backtestImportedReportBanner")
        self._set_banner_icon(banner, "clock", Palette.ACCENT)
        banner.action_button.clicked.connect(self._vm.requestExitImportedReportView)
        banner.setVisible(False)
        return self._tighten(banner)

    @staticmethod
    def _tighten(banner: Banner) -> Banner:
        """`Banner` is a `Panel`, so it inherits Qt's default layout margins.
        These three sit stacked above a chart and were built at 4px
        vertically; left at the default they each grow ~10px and push the
        chart down."""
        banner.body_layout.setContentsMargins(12, 4, 12, 4)
        return banner

    @staticmethod
    def _set_banner_icon(banner: Banner, name: str, colour: str) -> None:
        banner.icon_label.setPixmap(
            get_icon_loader().get_icon(name, colour, 14).pixmap(14, 14)
        )
        banner.icon_label.setVisible(True)

    # ------------------------------------------------------------------ #
    # Metrics header + stat cards / result box
    # ------------------------------------------------------------------ #

    def _build_metrics_header(self) -> QWidget:
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self._metrics_header = row_widget

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        bar = QFrame()
        bar.setFixedSize(3, 14)
        bar.setStyleSheet(
            f"background-color: {Palette.ACCENT}; border-radius: 2px; border: none;"
        )
        title_row.addWidget(bar)
        title = QLabel("BACKTEST PERFORMANCE METRICS")
        title.setStyleSheet(
            f"color: {Palette.TEXT_PRIMARY}; font-size: 12px; font-weight: bold; "
            f"letter-spacing: 0.8px; background: transparent; border: none;"
        )
        title_row.addWidget(title)
        self._btn_limitations = QPushButton()
        self._btn_limitations.setObjectName("btnBacktestLimitations")
        self._btn_limitations.setFlat(True)
        self._btn_limitations.setFixedSize(18, 18)
        self._btn_limitations.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_limitations.setIcon(
            get_icon_loader().get_icon("info", Palette.MUTED, 13)
        )
        self._btn_limitations.setToolTip("View this run's limitations")
        self._btn_limitations.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
        )
        self._btn_limitations.clicked.connect(self._vm.requestOpenLimitations)
        title_row.addWidget(self._btn_limitations)
        row.addLayout(title_row)

        row.addStretch(1)

        self._btn_expand_metrics = QPushButton("Expand")
        self._btn_expand_metrics.setObjectName("lnkExpandMetrics")
        self._btn_expand_metrics.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_expand_metrics.setFixedHeight(26)
        self._btn_expand_metrics.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {Palette.BG_CARD};"
            f"  border: 1px solid {Palette.BORDER};"
            f"  border-radius: 6px;"
            f"  padding: 2px 14px;"
            f"  color: {Palette.TEXT_PRIMARY};"
            f"  font-size: 11px;"
            f"  font-weight: 500;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {Palette.STATE_HOVER_BG};"
            f"  border-color: {Palette.STATE_NAV_BORDER};"
            f"}}"
        )
        self._btn_expand_metrics.clicked.connect(self._vm.requestOpenExtendedMetrics)
        row.addWidget(self._btn_expand_metrics)

        # BOT-095G — no `setStyleSheet()` here: the styling ratchet only falls.
        self._combo_run_history = QComboBox()
        self._combo_run_history.setObjectName("comboSessionRunHistory")
        self._combo_run_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self._combo_run_history.setFixedHeight(26)
        self._combo_run_history.setToolTip(
            "Redisplay an earlier run from this session, without re-running it"
        )
        self._combo_run_history.addItem(_RUN_HISTORY_PLACEHOLDER, "")
        self._combo_run_history.setEnabled(False)
        self._combo_run_history.currentIndexChanged.connect(
            self._on_run_history_selected
        )
        row.addWidget(self._combo_run_history)

        return row_widget

    def _build_result_warning_label(self) -> QLabel:
        label = QLabel()
        label.setObjectName("lblResultWarning")
        label.setStyleSheet(
            f"color: {Palette.WARNING}; font-size: 11px; font-weight: normal; "
            f"background: transparent; border: none; padding-top: 2px;"
        )
        label.setWordWrap(True)
        return label

    def _build_stat_cards_row(self) -> BacktestStatRow:
        # `EPIC-025` PR 4.3g: read-only tiles (HLD §11.3), after `EPIC-015`'s
        # `StatCardRow.qml` and `EPIC-007F`'s QtWidgets `StatCard` before it.
        # Callback-constructed — the widget reads `primaryStatCards` live, and
        # `_sync_stat_cards()` below only says *when* to re-pull that list.
        return BacktestStatRow(lambda: self._vm.run_result.primaryStatCards)

    def _build_result_box(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._result_text = QTextEdit()
        self._result_text.setObjectName("txtBacktestResult")
        self._result_text.setReadOnly(True)
        self._result_text.setFixedHeight(120)
        self._result_text.setStyleSheet(
            f"background-color: {Palette.BG_CARD}; border: 1px solid {Palette.BORDER}; "
            f"border-radius: 6px; color: {Palette.TEXT_PRIMARY}; font-size: 11px; "
            f"font-family: 'JetBrains Mono', 'Fira Code', monospace;"
        )
        layout.addWidget(self._result_text)

        self._btn_request_sync = QPushButton()
        self._btn_request_sync.setObjectName("btnRequestSync")
        self._btn_request_sync.setFixedHeight(34)
        self._btn_request_sync.clicked.connect(self._vm.requestSync)
        layout.addWidget(self._btn_request_sync, 0, Qt.AlignmentFlag.AlignLeft)

        return widget

    # ------------------------------------------------------------------ #
    # ViewModel wiring
    # ------------------------------------------------------------------ #

    def _wire_view_model(self) -> None:
        vm = self._vm
        vm.controlsEnabledChanged.connect(self._sync_controls_enabled)
        vm.uiModeChanged.connect(self._sync_controls_enabled)
        vm.isConfigDirtyChanged.connect(self._sync_banners)
        vm.run_progress.backtestProgressChanged.connect(self._sync_banners)
        vm.run_progress.syncProgressChanged.connect(self._sync_banners)
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
        running_like = mode in ("RUNNING", "CANCELLING", "SYNCING")
        self._progress_banner.setVisible(running_like)
        if running_like:
            cancelling = mode == "CANCELLING"
            self._progress_banner_widget.set_cancelling(cancelling)
            if cancelling:
                self._progress_banner_widget.set_status_text(CANCELLING_CAPTION)
                self._progress_banner_widget.set_indeterminate(True)
            elif mode == "SYNCING":
                self._progress_banner_widget.set_indeterminate(False)
                self._progress_banner_widget.set_status_text(
                    vm.run_progress.syncProgressText
                )
                self._progress_banner_widget.set_percent(
                    _clamp_percent(vm.run_progress.syncProgressPercent)
                )
            else:
                self._progress_banner_widget.set_indeterminate(False)
                self._progress_banner_widget.set_status_text(
                    vm.run_progress.backtestProgressText
                )
                self._progress_banner_widget.set_percent(
                    _clamp_percent(vm.run_progress.backtestProgressPercent)
                )

        self._preview_banner.setVisible(bool(vm.isChartPreview))

        self._stale_banner.setVisible(bool(vm.isConfigDirty))
        if vm.isConfigDirty:
            self._stale_banner.message = (
                f"Configuration changed ({vm.configDiffSummary}). "
                f"The results below have not been updated."
            )

        coverage_visible = (
            bool(vm.run_result.needsDataSync)
            and vm.run_result.dataCoverageMessage != ""
        )
        self._coverage_banner.setVisible(coverage_visible)
        if coverage_visible:
            self._coverage_banner.message = vm.run_result.dataCoverageMessage

        imported_report_visible = mode == "VIEWING_IMPORTED_REPORT" and bool(
            vm.importedReportBannerText
        )
        self._imported_report_banner.setVisible(imported_report_visible)
        if imported_report_visible:
            self._imported_report_banner.message = vm.importedReportBannerText

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
        self._result_text.setPlainText(vm.run_result.resultText)
        self._result_text.setStyleSheet(
            f"background-color: {Palette.BG_CARD}; border: 1px solid {Palette.BORDER}; "
            f"border-radius: 6px; color: {Palette.DANGER if vm.run_result.resultIsError else Palette.TEXT_PRIMARY}; "
            f"font-size: 11px; font-family: 'JetBrains Mono', 'Fira Code', monospace;"
        )
        self._btn_request_sync.setVisible(bool(vm.run_result.needsDataSync))
        self._btn_request_sync.setEnabled(vm.uiMode != "SYNCING")
        text = "Syncing..." if vm.uiMode == "SYNCING" else "Sync data now"
        self._btn_request_sync.setText(text)
        self._btn_request_sync.setStyleSheet(
            f"background-color: {Palette.ACCENT if self._btn_request_sync.isEnabled() else Palette.STATE_NAV_BORDER}; "
            f"color: {Palette.BG}; font-size: 12px; font-weight: bold; border-radius: 6px; border: none;"
        )
