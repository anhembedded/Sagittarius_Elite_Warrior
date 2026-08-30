"""EPIC-006E: `BackTestTopPanel.qml` -> QtWidgets.

Toolbar (symbol/strategy/timeframe/range/timezone/capital/order-exec/
indicator pickers + bot-params + run button), progress/preview/stale/
coverage banners, and the performance stat-cards row — everything above
the chart. Behaviour-preserving port: every `objectName` from the QML
carries over unchanged (tests/presenter both key off them).

`EPIC-015` Phase 4 replaced two pieces of that QtWidgets port with QML
embeds sitting directly beside this screen's chart — `ProgressBannerWidget`
(`qml/kit/`) for the run/sync progress banner, `StatCardRowWidget`
(`qml/StatCardRow/`) for the primary performance stat-cards row. Their
QtWidgets predecessors' `objectName`s (`btnCancelBacktestProgress`, the
per-card `cardMetric_N` as a `QWidget`) do not carry over as widget
attributes — the cancel button and each stat card now live inside a QML
scene, reached by `objectName` through `qml_item()`
(`tests/conftest.py`), same as every other `Repeater`/QML-scene lookup in
this rollout. `backtestProgressBanner` (the outer `QFrame`) and the four
`_sync_*`/`_build_*` method names are unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Banner,
    Severity,
    StyleRole,
    apply_role,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.kit.progress_banner_widget import (
    ProgressBannerWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.StatCardRow.stat_card_row_widget import (
    StatCardRowWidget,
)

if TYPE_CHECKING:
    from .backtest_view_model import BackTestViewModel

#: Same fixed height Data Management's Phase 2 embed uses for the same
#: `ProgressBanner.qml` content (`data_management_view.py`'s
#: `_PROGRESS_BANNER_HEIGHT`) — a `QQuickWidget` with `SizeRootObjectToView`
#: has no natural size of its own, unlike the `AppProgressBar` it replaces.
_PROGRESS_BANNER_HEIGHT = 32

#: `StatCardRow.qml` cards have container styling (background, border,
#: rounded corners, and padding) with title, value, and subtitle/badge.
#: 82px accommodates all lines comfortably without vertical clipping.
_STAT_CARD_ROW_HEIGHT = 82


def _clamp_percent(value: float) -> float:
    """@brief `BackTestViewModel.backtestProgressPercent`/`syncProgressPercent`
    to the 0..100 range `ProgressBanner.qml` expects.

    @details Unlike `DataManagementViewModel.progressPercent` (clamped at
    the property getter itself), these two properties store whatever
    `set_backtest_progress()`/`set_sync_progress()` were last called with,
    with no clamp of their own. Every real caller today already clamps
    before calling (`backtest_presenter.py`'s
    `_on_backtest_progress_for_action`/`_on_sync_progress_for_action` both
    do `min(100.0, max(0.0, ...))`), so this is a defensive backstop, not a
    fix for an observed bug: `ProgressBanner.qml`'s bar *width* already
    clamps its own fraction (`Math.max(0, Math.min(1, root.percent / 100))`),
    but its percent *text* (`Math.round(root.percent) + "%"`) does not — an
    unclamped value would show e.g. "150%" text beside a visually full bar.
    """
    return min(100.0, max(0.0, value))


def _pill_button(object_name: str, min_width: int = 0) -> QPushButton:
    btn = QPushButton()
    btn.setObjectName(object_name)
    btn.setFlat(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(34)
    if min_width:
        btn.setMinimumWidth(min_width)
    return btn


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

        card_layout.addWidget(self._build_toolbar())
        self._progress_banner = self._build_progress_banner()
        card_layout.addWidget(self._progress_banner)
        self._preview_banner = self._build_preview_banner()
        card_layout.addWidget(self._preview_banner)
        self._stale_banner = self._build_stale_banner()
        card_layout.addWidget(self._stale_banner)
        self._coverage_banner = self._build_coverage_banner()
        card_layout.addWidget(self._coverage_banner)
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
    # Toolbar (Row 1)
    # ------------------------------------------------------------------ #

    def _build_toolbar(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("toolbarScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setFixedHeight(52)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
            f"QScrollArea > QWidget > QWidget {{ background: transparent; }}"
            f"QScrollBar:horizontal {{ height: 4px; background: transparent; border: none; margin: 0; }}"
            f"QScrollBar::handle:horizontal {{ background: {Palette.BORDER}; border-radius: 2px; }}"
            f"QScrollBar::handle:horizontal:hover {{ background: {Palette.STATE_NAV_BORDER}; }}"
            f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; height: 0px; background: none; border: none; }}"
        )
        scroll.viewport().setStyleSheet("background: transparent;")

        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setObjectName("toolbarRow")
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self._btn_symbol = self._icon_text_button(
            "btnBacktestSymbol", "dollar-sign", Palette.ACCENT, min_width=110
        )
        self._btn_symbol.clicked.connect(self._vm.requestOpenSymbolPicker)
        row.addWidget(self._btn_symbol)

        self._btn_strategy = self._icon_text_button(
            "btnBacktestStrategy",
            "briefcase",
            Palette.ACCENT,
            min_width=260,
            value_color=Palette.ACCENT,
        )
        self._btn_strategy.clicked.connect(self._vm.requestOpenStrategyPicker)
        row.addWidget(self._btn_strategy)

        self._btn_timeframe = self._icon_text_button(
            "btnBacktestTimeframe", None, None, min_width=70
        )
        self._btn_timeframe.clicked.connect(self._vm.requestOpenTimeframePicker)
        row.addWidget(self._btn_timeframe)

        self._btn_range = self._icon_text_button(
            "btnBacktestRange", "calendar", Palette.ACCENT, min_width=140
        )
        self._btn_range.clicked.connect(self._vm.requestOpenTimeRangePicker)
        row.addWidget(self._btn_range)

        self._btn_timezone = self._icon_text_button(
            "btnBacktestTimezone", "clock", Palette.ACCENT, min_width=130
        )
        self._btn_timezone.setToolTip(
            "Chỉ đổi giờ hiển thị. Dữ liệu và Backtest luôn tính theo UTC."
        )
        self._btn_timezone.clicked.connect(self._vm.requestOpenTimezonePicker)
        row.addWidget(self._btn_timezone)

        self._btn_capital = self._icon_text_button(
            "btnBacktestCapital", "dollar-sign", Palette.SUCCESS, min_width=110
        )
        self._btn_capital.clicked.connect(
            lambda: self._vm.requestOpenCapital(*self._popup_pos(self._btn_capital))
        )
        row.addWidget(self._btn_capital)

        self._btn_order_exec = _pill_button("btnBacktestOrderExecution", min_width=95)
        self._btn_order_exec.setStyleSheet(self._field_button_style())
        self._btn_order_exec.setLayout(
            self._icon_label_row("briefcase", Palette.ACCENT, "Tập lệnh")
        )
        self._btn_order_exec.clicked.connect(
            lambda: self._vm.requestOpenOrderExecution(
                *self._popup_pos(self._btn_order_exec)
            )
        )
        row.addWidget(self._btn_order_exec)

        self._btn_indicator_picker = _pill_button(
            "btnBacktestIndicatorPicker", min_width=90
        )
        self._btn_indicator_picker.setStyleSheet(self._field_button_style())
        self._btn_indicator_picker.setLayout(
            self._icon_label_row("sliders", Palette.ACCENT, "Chỉ báo")
        )
        self._btn_indicator_picker.clicked.connect(
            lambda: self._vm.requestOpenIndicatorPicker(
                *self._popup_pos(self._btn_indicator_picker)
            )
        )
        row.addWidget(self._btn_indicator_picker)

        row.addStretch(1)

        self._btn_bot_params = _pill_button("btnBacktestBotParams", min_width=175)
        self._btn_bot_params.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.BG_CARD_HEADER}; "
            f"border: 1px solid {Palette.STATE_NAV_BORDER}; "
            f"border-radius: 6px; }} "
            f"QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }}"
        )
        self._btn_bot_params.setLayout(
            self._icon_label_row("sliders", Palette.ACCENT, "Thông số Chiến lược")
        )
        self._btn_bot_params.clicked.connect(
            lambda: self._vm.requestOpenBotParams(self._vm.selectedStrategyName)
        )
        row.addWidget(self._btn_bot_params)

        self._btn_run = _pill_button("btnRunBacktest", min_width=145)
        run_row = QHBoxLayout()
        run_row.setContentsMargins(0, 0, 0, 0)
        run_row.setSpacing(8)
        self._run_icon_label = QLabel()
        run_row.addWidget(self._run_icon_label)
        self._run_text_label = QLabel()
        self._run_text_label.setStyleSheet(
            f"color: {Palette.BG}; font-size: 11px; font-weight: bold; background: transparent; border: none;"
        )
        run_row.addWidget(self._run_text_label)
        self._btn_run.setLayout(run_row)
        self._btn_run.clicked.connect(self._on_run_clicked)
        # Not added to `row`: `BackTestView` places this in `PageShell`'s
        # header actions instead — the header's primary action, per the
        # Pattern Library, not another item in the "which data am I
        # looking at" context bar this toolbar has become.

        scroll.setWidget(row_widget)
        return scroll

    @property
    def run_button(self) -> QPushButton:
        """Public accessor for `BackTestView` to place in the page header —
        `_btn_run` itself stays the private attribute every existing test
        and this class's own `_sync_run_button` already key off."""
        return self._btn_run

    def _icon_text_button(
        self,
        object_name: str,
        icon_name: str | None,
        icon_color: str | None,
        *,
        min_width: int = 0,
        value_color: str | None = None,
    ) -> QPushButton:
        btn = _pill_button(object_name, min_width)
        btn.setStyleSheet(self._field_button_style())
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)
        if icon_name:
            icon_label = QLabel()
            icon_label.setPixmap(
                get_icon_loader().get_icon(icon_name, icon_color, 13).pixmap(13, 13)
            )
            icon_label.setStyleSheet("background: transparent; border: none;")
            layout.addWidget(icon_label)
        text_label = QLabel()
        text_label.setObjectName("_valueLabel")
        text_label.setStyleSheet(
            f"color: {value_color or Palette.TEXT_PRIMARY}; font-size: 11px; "
            f"font-weight: bold; background: transparent; border: none;"
        )
        layout.addWidget(text_label, 1)
        chevron = QLabel()
        chevron.setPixmap(
            get_icon_loader().get_icon("chevron-down", Palette.MUTED, 11).pixmap(11, 11)
        )
        chevron.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(chevron)
        btn.setLayout(layout)
        btn._value_label = text_label  # type: ignore[attr-defined]
        return btn

    def _icon_label_row(
        self, icon_name: str, icon_color: str, text: str
    ) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(6)
        icon_label = QLabel()
        icon_label.setPixmap(
            get_icon_loader().get_icon(icon_name, icon_color, 13).pixmap(13, 13)
        )
        icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(icon_label)
        text_label = QLabel(text)
        text_label.setStyleSheet(
            f"color: {Palette.TEXT_PRIMARY}; font-size: 11px; font-weight: bold; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(text_label)
        return layout

    @staticmethod
    def _field_button_style() -> str:
        return (
            f"QPushButton {{ background-color: {Palette.STATE_IDLE_BG}; border: 1px solid "
            f"{Palette.STATE_NAV_BORDER}; border-radius: 6px; }} "
            f"QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }}"
        )

    @staticmethod
    def _popup_pos(button: QPushButton) -> tuple[float, float]:
        global_pos = button.mapToGlobal(button.rect().bottomLeft())
        return float(global_pos.x()), float(global_pos.y() + 4)

    # ------------------------------------------------------------------ #
    # Banners
    # ------------------------------------------------------------------ #

    def _build_progress_banner(self) -> QFrame:
        banner = QFrame()
        banner.setObjectName("backtestProgressBanner")
        # EPIC-015 Phase 4: `ProgressBannerWidget` (QML) replaces
        # `AppProgressBar` + a standalone Cancel `QPushButton` — the same
        # swap Data Management's Phase 2 already made
        # (`data_management_view.py`). This bordered `QFrame` is kept as-is,
        # unlike Data Management's own plain container: this banner sits
        # *inside* an already-SURFACE-styled `self._card`, so it still needs
        # its own nested background/border to read as a distinct strip, same
        # as before the swap.
        banner.setStyleSheet(
            f"QFrame {{ background-color: {Palette.BG_CARD}; "
            f"border: 1px solid {Palette.STATE_NAV_BORDER}; border-radius: 6px; }}"
        )
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(12, 4, 12, 4)
        self._progress_banner_widget = ProgressBannerWidget()
        self._progress_banner_widget.setFixedHeight(_PROGRESS_BANNER_HEIGHT)
        self._progress_banner_widget.cancelRequested.connect(
            self._vm.requestCancelBacktest
        )
        layout.addWidget(self._progress_banner_widget, 1)
        banner.setVisible(False)
        return banner

    def _build_preview_banner(self) -> Banner:
        banner = Banner(
            'Đồ thị xem trước — chưa chạy Backtest. Nhấn "CHẠY BACKTEST" để xem '
            "kết quả thật.",
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
        banner = Banner(severity=Severity.WARN, action_text="Chạy lại ngay")
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
        title = QLabel("CHỈ SỐ HIỆU SUẤT BACKTEST")
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
        self._btn_limitations.setToolTip("Xem giới hạn của lần chạy này")
        self._btn_limitations.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
        )
        self._btn_limitations.clicked.connect(self._vm.requestOpenLimitations)
        title_row.addWidget(self._btn_limitations)
        row.addLayout(title_row)

        row.addStretch(1)

        self._btn_expand_metrics = QPushButton("Mở rộng")
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

    def _build_stat_cards_row(self) -> StatCardRowWidget:
        # EPIC-015 Phase 4: `StatCardRow.qml` (a `Repeater` of `StatCard.qml`
        # delegates) replaces per-run construction/teardown of the
        # QtWidgets `StatCard` (`kit/surfaces/stat_card.py`). Callback-
        # constructed (`qml-rule.md` §1.1) — this widget reads
        # `primaryStatCards` live, `_sync_stat_cards()` below only tells it
        # *when* to re-pull that list, not what is in it.
        widget = StatCardRowWidget(lambda: self._vm.primaryStatCards)
        widget.setFixedHeight(_STAT_CARD_ROW_HEIGHT)
        return widget

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
        vm.selectedSymbolChanged.connect(self._sync_toolbar_labels)
        vm.selectedStrategyKeyChanged.connect(self._sync_toolbar_labels)
        vm.selectedTimeframeChanged.connect(self._sync_toolbar_labels)
        vm.timeRangePresetChanged.connect(self._sync_toolbar_labels)
        vm.displayTimezoneChanged.connect(self._sync_toolbar_labels)
        vm.initialCapitalTextChanged.connect(self._sync_toolbar_labels)
        vm.selectedCurrencyChanged.connect(self._sync_toolbar_labels)
        vm.controlsEnabledChanged.connect(self._sync_controls_enabled)
        vm.uiModeChanged.connect(self._sync_controls_enabled)
        vm.uiModeChanged.connect(self._sync_run_button)
        vm.isConfigDirtyChanged.connect(self._sync_run_button)
        vm.isConfigDirtyChanged.connect(self._sync_banners)
        vm.backtestProgressChanged.connect(self._sync_banners)
        vm.syncProgressChanged.connect(self._sync_banners)
        vm.uiModeChanged.connect(self._sync_banners)
        vm.isChartPreviewChanged.connect(self._sync_banners)
        vm.dataCoverageChanged.connect(self._sync_banners)
        vm.needsDataSyncChanged.connect(self._sync_banners)
        vm.configDiffSummaryChanged.connect(self._sync_banners)
        vm.statCardsChanged.connect(self._sync_stat_cards)
        vm.statCardsChanged.connect(self._sync_metrics_header)
        vm.resultWarningTextChanged.connect(self._sync_metrics_header)
        vm.resultChanged.connect(self._sync_result_box)
        vm.needsDataSyncChanged.connect(self._sync_result_box)

    def _sync_all(self) -> None:
        self._sync_toolbar_labels()
        self._sync_controls_enabled()
        self._sync_run_button()
        self._sync_banners()
        self._sync_stat_cards()
        self._sync_metrics_header()
        self._sync_result_box()

    def _sync_toolbar_labels(self) -> None:
        vm = self._vm
        self._btn_symbol._value_label.setText(vm.selectedSymbol or "Symbol")  # type: ignore[attr-defined]
        self._btn_strategy._value_label.setText(vm.selectedStrategyName)  # type: ignore[attr-defined]
        self._btn_timeframe._value_label.setText(vm.selectedTimeframe or "1m")  # type: ignore[attr-defined]
        self._btn_range._value_label.setText(vm.selectedTimeRangePresetLabel)  # type: ignore[attr-defined]
        self._btn_timezone._value_label.setText(vm.displayTimezoneLabel)  # type: ignore[attr-defined]
        capital = vm.initialCapitalText or "0"
        self._btn_capital._value_label.setText(f"{capital} {vm.selectedCurrency}")  # type: ignore[attr-defined]

    def _sync_controls_enabled(self) -> None:
        enabled = bool(self._vm.controlsEnabled)
        for btn in (
            self._btn_symbol,
            self._btn_strategy,
            self._btn_timeframe,
            self._btn_range,
            self._btn_timezone,
            self._btn_capital,
            self._btn_bot_params,
        ):
            btn.setEnabled(enabled)

    def _sync_run_button(self) -> None:
        vm = self._vm
        mode = vm.uiMode
        is_cancellable = mode in ("RUNNING", "SYNCING")
        self._btn_run.setEnabled(
            mode != "CANCELLING" and (bool(vm.controlsEnabled) or is_cancellable)
        )
        if is_cancellable:
            color, hover_color = Palette.DANGER, Palette.DANGER
            icon_name = "square"
        elif vm.isConfigDirty:
            color, hover_color = Palette.WARNING, Palette.WARNING
            icon_name = "rotate-ccw"
        else:
            color, hover_color = Palette.SUCCESS, Palette.SUCCESS
            icon_name = "play"
        self._btn_run.setStyleSheet(
            f"QPushButton {{ background-color: {color}; border-radius: 6px; border: none; }} "
            f"QPushButton:hover {{ background-color: {hover_color}; }} "
            f"QPushButton:disabled {{ background-color: {Palette.STATE_HOVER_BG}; }}"
        )
        self._run_icon_label.setPixmap(
            get_icon_loader().get_icon(icon_name, Palette.BG, 13).pixmap(13, 13)
        )
        if mode == "CANCELLING":
            text = "ĐANG HỦY..."
        elif mode == "RUNNING":
            text = "HỦY BACKTEST"
        elif mode == "SYNCING":
            text = "HỦY ĐỒNG BỘ"
        elif vm.isConfigDirty:
            text = "CẬP NHẬT LẠI"
        else:
            text = "CHẠY BACKTEST"
        self._run_text_label.setText(text)

    def _on_run_clicked(self) -> None:
        mode = self._vm.uiMode
        if mode in ("RUNNING", "SYNCING"):
            self._vm.requestCancelBacktest()
        else:
            self._vm.requestRun()

    def _sync_banners(self) -> None:
        vm = self._vm
        mode = vm.uiMode
        running_like = mode in ("RUNNING", "CANCELLING", "SYNCING")
        self._progress_banner.setVisible(running_like)
        if running_like:
            cancelling = mode == "CANCELLING"
            self._progress_banner_widget.set_cancelling(cancelling)
            if cancelling:
                self._progress_banner_widget.set_status_text("Đang hủy an toàn...")
                self._progress_banner_widget.set_indeterminate(True)
            elif mode == "SYNCING":
                self._progress_banner_widget.set_indeterminate(False)
                self._progress_banner_widget.set_status_text(vm.syncProgressText)
                self._progress_banner_widget.set_percent(
                    _clamp_percent(vm.syncProgressPercent)
                )
            else:
                self._progress_banner_widget.set_indeterminate(False)
                self._progress_banner_widget.set_status_text(vm.backtestProgressText)
                self._progress_banner_widget.set_percent(
                    _clamp_percent(vm.backtestProgressPercent)
                )

        self._preview_banner.setVisible(bool(vm.isChartPreview))

        self._stale_banner.setVisible(bool(vm.isConfigDirty))
        if vm.isConfigDirty:
            self._stale_banner.message = (
                f"Cấu hình đã thay đổi ({vm.configDiffSummary}). "
                f"Kết quả bên dưới chưa được cập nhật."
            )

        coverage_visible = bool(vm.needsDataSync) and vm.dataCoverageMessage != ""
        self._coverage_banner.setVisible(coverage_visible)
        if coverage_visible:
            self._coverage_banner.message = vm.dataCoverageMessage

    def _sync_stat_cards(self) -> None:
        has_cards = bool(self._vm.primaryStatCards)
        self._stat_cards_row.setVisible(has_cards)
        self._result_box.setVisible(not has_cards)
        if has_cards:
            # `StatCardRow.qml`'s `Repeater` reads `vm.cards` off
            # `StatCardRowVM`, not `BackTestViewModel.primaryStatCards`
            # directly — `refresh()` is the one call that re-pulls and
            # re-converts it (`qml-rule.md` §4.2: safe to call every time,
            # since a full delegate rebuild is what a `Repeater` over a
            # list-of-dicts model always does on any change, not something
            # this call triggers additionally).
            self._stat_cards_row.refresh()

    def _sync_metrics_header(self) -> None:
        has_cards = bool(self._vm.primaryStatCards)
        self._metrics_header.setVisible(has_cards)
        text = self._vm.resultWarningText
        self._result_warning_label.setText(text)
        self._result_warning_label.setVisible(has_cards and bool(text))

    def _sync_result_box(self) -> None:
        vm = self._vm
        self._result_text.setPlainText(vm.resultText)
        self._result_text.setStyleSheet(
            f"background-color: {Palette.BG_CARD}; border: 1px solid {Palette.BORDER}; "
            f"border-radius: 6px; color: {Palette.DANGER if vm.resultIsError else Palette.TEXT_PRIMARY}; "
            f"font-size: 11px; font-family: 'JetBrains Mono', 'Fira Code', monospace;"
        )
        self._btn_request_sync.setVisible(bool(vm.needsDataSync))
        self._btn_request_sync.setEnabled(vm.uiMode != "SYNCING")
        text = "Đang đồng bộ..." if vm.uiMode == "SYNCING" else "Đồng bộ dữ liệu ngay"
        self._btn_request_sync.setText(text)
        self._btn_request_sync.setStyleSheet(
            f"background-color: {Palette.ACCENT if self._btn_request_sync.isEnabled() else Palette.STATE_NAV_BORDER}; "
            f"color: {Palette.BG}; font-size: 12px; font-weight: bold; border-radius: 6px; border: none;"
        )
