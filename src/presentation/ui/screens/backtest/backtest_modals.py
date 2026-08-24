"""EPIC-006E3: Backtest's 11 modal QMLs (orchestrated by
`BackTestModals.qml`) -> `Overlay`-based `QDialog`s.

`BotParamsDialog.qml` (200 lines) was NOT ported — verified dead: never
instantiated anywhere (`BackTestModals.qml` only ever built
`StrategyPropertiesModal`, BOT-104's superseding 4-tab dialog). Porting it
would have been wasted work; `git grep 'BotParamsDialog {'` confirms zero
instantiations.

Each dialog is built lazily by `BackTestModalsHost` (this module's
orchestrator, replacing `BackTestModals.qml` + Engine's `OverlayHost`/
`QQuickWidget` — a real `QDialog` is already modal and self-positioning,
so the full-window click-through overlay QML needed no longer applies)
and wired directly to `BackTestViewModel`'s `openXRequested` signals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from sagittarius_engine.extensions.pyside_mvc.widgets import Overlay, SelectableCard

from .backtest_widgets import MetricCardWidget

if TYPE_CHECKING:
    from .backtest_view_model import BackTestViewModel

_FIELD_STYLE = (
    "background-color: #181a26; border: 1px solid #2a2d3e; border-radius: 4px; "
    f"color: {Palette.TEXT_PRIMARY}; padding: 0 6px;"
)
_ACCENT = Palette.ACCENT


def _field_row(label_text: str, field: QWidget) -> QVBoxLayout:
    column = QVBoxLayout()
    column.setSpacing(4)
    label = QLabel(label_text)
    label.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 11px;")
    column.addWidget(label)
    field.setFixedHeight(32)
    field.setStyleSheet(_FIELD_STYLE)
    column.addWidget(field)
    return column


def _section_header(icon_text: str, text: str) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(6)
    label = QLabel(text.upper())
    label.setStyleSheet(
        f"color: {_ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;"
    )
    row.addWidget(label)
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("background-color: #2a2d3e; border: none; max-height: 1px;")
    row.addWidget(line, 1)
    return row


def _selectable_list_card(
    object_name: str, text: str, subtitle: str, is_selected: bool
) -> SelectableCard:
    """One row of a single-select picker list (Strategy/TimeRange/Timezone)
    — a `SelectableCard` (engine, `pyside_mvc.widgets`) rather than a
    hand-styled `QPushButton`: this "click to choose, accent border when
    selected" shape repeats across 5 Backtest pickers (this list style plus
    the grid style `_selectable_grid_card()` below), enough real instances
    to promote past an app-local escape hatch."""
    card = SelectableCard()
    card.setObjectName(object_name)
    card.selected = is_selected
    card.body_layout.setContentsMargins(12, 6, 12, 6)
    card.body_layout.setSpacing(2)
    title_label = QLabel(text)
    title_label.setStyleSheet(
        f"color: {_ACCENT if is_selected else Palette.TEXT_PRIMARY}; font-size: 12px; "
        f"font-weight: {'bold' if is_selected else 'normal'}; border: none; background: transparent;"
    )
    card.body_layout.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 10px; border: none; background: transparent;"
        )
        card.body_layout.addWidget(subtitle_label)
    card.setMinimumHeight(46 if subtitle else 40)
    return card


def _selectable_grid_card(text: str, is_selected: bool) -> SelectableCard:
    """One cell of a grid picker (Timeframe/Symbol) — same `SelectableCard`
    as `_selectable_list_card()`, centered single-line content instead of
    a stacked title/subtitle."""
    card = SelectableCard()
    card.selected = is_selected
    card.setFixedHeight(38)
    card.body_layout.setContentsMargins(6, 4, 6, 4)
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"color: {_ACCENT if is_selected else Palette.TEXT_PRIMARY}; font-size: 12px; "
        f"font-weight: {'bold' if is_selected else 'normal'}; border: none; background: transparent;"
    )
    card.body_layout.addWidget(label)
    return card


# ====================================================================== #
# 1. Capital Dialog
# ====================================================================== #


class CapitalDialogWidget(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("THIẾT LẬP VỐN BAN ĐẦU", parent=parent)
        self.setObjectName("capitalDialog")
        self._vm = view_model
        self.resize(360, 190)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._capital_input = QLineEdit()
        self._capital_input.setObjectName("txtBacktestCapital")
        self._capital_input.setValidator(QDoubleValidator(0.0, 1e15, 8))
        self._capital_input.setFixedHeight(34)
        self._capital_input.textChanged.connect(view_model.requestCapitalValidation)
        row.addWidget(self._capital_input, 1)

        self._currency_combo = QComboBox()
        self._currency_combo.setObjectName("cboBacktestCurrency")
        self._currency_combo.setFixedSize(90, 34)
        self._currency_combo.addItems(view_model.currencyOptions)
        row.addWidget(self._currency_combo)
        self.body_layout.addLayout(row)

        self._validation_label = QLabel()
        self._validation_label.setObjectName("txtCapitalValidationMessage")
        self._validation_label.setWordWrap(True)
        self._validation_label.setStyleSheet(
            f"color: {Palette.DANGER}; font-size: 10px;"
        )
        self._validation_label.setVisible(False)
        self.body_layout.addWidget(self._validation_label)

        view_model.capitalValidationMessageChanged.connect(self._sync_validation)

        self._btn_apply: QPushButton | None = None

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setObjectName("btnCancelCapital")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)
        self._btn_apply = QPushButton("Áp dụng")
        self._btn_apply.setObjectName("btnApplyCapital")
        self._btn_apply.clicked.connect(self._on_apply)
        row.addWidget(self._btn_apply)
        return row

    def _sync_validation(self) -> None:
        message = self._vm.capitalValidationMessage
        self._validation_label.setText(message)
        self._validation_label.setVisible(bool(message))
        if self._btn_apply is not None:
            self._btn_apply.setEnabled(not message)

    def open_dialog(self) -> None:
        self._capital_input.setText(self._vm.initialCapitalText)
        self._vm.requestCapitalValidation(self._capital_input.text())
        idx = self._currency_combo.findText(self._vm.selectedCurrency)
        if idx >= 0:
            self._currency_combo.setCurrentIndex(idx)
        self.show()
        self.raise_()

    def _on_apply(self) -> None:
        self._vm.initialCapitalText = self._capital_input.text()
        self._vm.selectedCurrency = self._currency_combo.currentText()
        self.accept()


# ====================================================================== #
# 2. Extended Metrics Modal
# ====================================================================== #


class ExtendedMetricsDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("CHỈ SỐ CHI TIẾT BACKTEST", parent=parent)
        self.setObjectName("extendedMetricsPopup")
        self._vm = view_model
        self.resize(480, 606)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._grid = QGridLayout(content)
        self._grid.setSpacing(12)
        scroll.setWidget(content)
        self.body_layout.addWidget(scroll)

        view_model.statCardsChanged.connect(self._sync)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for index, card_data in enumerate(self._vm.extendedStatCards):
            card = MetricCardWidget()
            card.setObjectName(f"cardExtendedMetric_{index}")
            card.set_data(
                title=card_data.get("title", ""),
                value=card_data.get("value", ""),
                value_color=Palette.TEXT_PRIMARY,
                suffix=card_data.get("suffix", ""),
                badge_text="",
                badge_color="",
            )
            self._grid.addWidget(card, index // 2, index % 2)


# ====================================================================== #
# 3. Limitations Modal
# ====================================================================== #


class LimitationsDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("GIỚI HẠN CỦA LẦN CHẠY NÀY", parent=parent)
        self.setObjectName("limitationsPopup")
        self._vm = view_model
        self.resize(480, 420)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._list_layout = QVBoxLayout(content)
        self._list_layout.setSpacing(10)
        scroll.setWidget(content)
        self.body_layout.addWidget(scroll)

        view_model.limitationsChanged.connect(self._sync)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for index, text in enumerate(self._vm.limitations):
            row = QHBoxLayout()
            row.setSpacing(10)
            bullet = QLabel("•")
            bullet.setStyleSheet(
                f"color: {Palette.MUTED}; font-size: 13px; font-weight: bold;"
            )
            row.addWidget(bullet)
            label = QLabel(text)
            label.setObjectName(f"lblLimitation_{index}")
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 11px;")
            row.addWidget(label, 1)
            self._list_layout.addLayout(row)


# ====================================================================== #
# 4. Indicator Picker Modal
# ====================================================================== #


class IndicatorPickerDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("CHỈ BÁO THAM KHẢO", parent=parent)
        self.setObjectName("indicatorPickerModal")
        self._vm = view_model
        self.resize(360, 300)

        self._empty_label = QLabel("Chưa có tập lệnh chỉ báo nào được đăng ký.")
        self._empty_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        self.body_layout.addWidget(self._empty_label)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(8)
        self.body_layout.addLayout(self._list_layout)

        view_model.script_model.modelReset.connect(self._sync)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        model = self._vm.script_model
        row_count = model.rowCount()
        self._empty_label.setVisible(row_count == 0)
        for row in range(row_count):
            index = model.index(row, 0)
            key = model.data(index, model.KeyRole)
            title = model.data(index, model.TitleRole)
            enabled = bool(model.data(index, model.EnabledRole))
            checkbox = QCheckBox(title)
            checkbox.setObjectName(f"chkBacktestScript_{key}")
            checkbox.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 12px;")
            checkbox.setChecked(enabled)
            checkbox.toggled.connect(
                lambda checked, r=row: model.setEnabled(r, checked)
            )
            self._list_layout.addWidget(checkbox)


# ====================================================================== #
# 5. Order Execution Modal
# ====================================================================== #

_EXECUTION_TRIGGERS = (
    ("On bar close", True, ""),
    ("Khi lệnh được khớp", True, ""),
    (
        "Trên mỗi tick của thanh lịch sử",
        False,
        (
            "Chế độ này dùng nến 1 giây, tách biệt hoàn toàn với nến bạn đã đồng bộ ở khung "
            "thời gian khác — sẽ cần đồng bộ lại dữ liệu riêng cho khung 1 giây."
        ),
    ),
    ("Trên mỗi tick của thanh thời gian thực", True, ""),
)
_HISTORICAL_TICK_INDEX = 2


class OrderExecutionDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("THỰC THI TẬP LỆNH", parent=parent)
        self.setObjectName("orderExecutionModal")
        self._vm = view_model
        self.resize(400, 250)

        self._checkboxes: list[QCheckBox] = []
        for index, (text, locked, tooltip) in enumerate(_EXECUTION_TRIGGERS):
            row = QHBoxLayout()
            row.setSpacing(10)
            checkbox = QCheckBox()
            checkbox.setObjectName(f"triggerCheckBox_{index}")
            checkbox.setEnabled(not locked)
            row.addWidget(checkbox)
            label = QLabel(text)
            label.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 12px;")
            row.addWidget(label, 1)
            if tooltip:
                label.setToolTip(tooltip)
                checkbox.setToolTip(tooltip)
            container = QWidget()
            container.setObjectName(f"chkExecutionTrigger_{index}")
            container.setLayout(row)
            self.body_layout.addWidget(container)
            checkbox.toggled.connect(
                lambda checked, i=index: self._on_toggled(i, checked)
            )
            self._checkboxes.append(checkbox)

        view_model.executionModeChanged.connect(self._sync)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        is_realtime = self._vm.executionMode == "HISTORICAL_TICK"
        for checkbox in self._checkboxes:
            checkbox.blockSignals(True)
        self._checkboxes[0].setChecked(not is_realtime)
        self._checkboxes[_HISTORICAL_TICK_INDEX].setChecked(is_realtime)
        for checkbox in self._checkboxes:
            checkbox.blockSignals(False)

    def _on_toggled(self, index: int, checked: bool) -> None:
        if index != _HISTORICAL_TICK_INDEX:
            return
        self._vm.executionMode = "HISTORICAL_TICK" if checked else "BAR_CLOSE"


# ====================================================================== #
# 6. Strategy Picker Modal
# ====================================================================== #


class StrategyPickerDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("CHỌN CHIẾN LƯỢC BOT", parent=parent)
        self.setObjectName("strategyPickerModal")
        self._vm = view_model
        self.resize(440, 320)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._list_layout = QVBoxLayout(content)
        self._list_layout.setSpacing(8)
        scroll.setWidget(content)
        self.body_layout.addWidget(scroll)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for option in self._vm.strategyOptions:
            key = option.get("key", "")
            is_selected = key == self._vm.selectedStrategyKey
            btn = _selectable_list_card(
                "", option.get("name", key), f"Mã: {key}", is_selected
            )
            btn.clicked.connect(lambda _checked=False, k=key: self._on_selected(k))
            self._list_layout.addWidget(btn)

    def _on_selected(self, key: str) -> None:
        self._vm.selectedStrategyKey = key
        self.accept()


# ====================================================================== #
# 7. Timeframe Picker Modal
# ====================================================================== #


class TimeframePickerDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("CHỌN KHUNG THỜI GIAN", parent=parent)
        self.setObjectName("timeframePickerModal")
        self._vm = view_model
        self.resize(380, 240)
        self._grid = QGridLayout()
        self._grid.setSpacing(10)
        self.body_layout.addLayout(self._grid)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        options = list(self._vm.timeframeOptions)
        for index, value in enumerate(options):
            is_selected = value == self._vm.selectedTimeframe
            card = _selectable_grid_card(value, is_selected)
            card.clicked.connect(lambda v=value: self._on_selected(v))
            self._grid.addWidget(card, index // 4, index % 4)

    def _on_selected(self, value: str) -> None:
        self._vm.selectedTimeframe = value
        self.accept()


# ====================================================================== #
# 8. Symbol Picker Modal
# ====================================================================== #


class BacktestSymbolPickerDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("CHỌN SYMBOL", parent=parent)
        self.setObjectName("symbolPickerModal")
        self._vm = view_model
        self.resize(420, 320)

        self._search_field = QLineEdit()
        self._search_field.setObjectName("txtSymbolSearch")
        self._search_field.setPlaceholderText("Tìm symbol (vd: BTC)")
        self._search_field.textChanged.connect(lambda _text: self._sync())
        self.body_layout.addWidget(self._search_field)

        self._loading_label = QLabel("Đang tải danh sách symbol từ sàn...")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 12px;")
        self.body_layout.addWidget(self._loading_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._grid = QGridLayout(content)
        self._grid.setSpacing(8)
        scroll.setWidget(content)
        self.body_layout.addWidget(scroll)
        self._scroll = scroll

        view_model.symbolOptionsChanged.connect(self._sync)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        options = list(self._vm.symbolOptions)
        has_options = bool(options)
        self._search_field.setVisible(has_options)
        self._loading_label.setVisible(not has_options)
        self._scroll.setVisible(has_options)

        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        query = self._search_field.text().upper()
        filtered = [s for s in options if not query or query in s]
        for index, symbol in enumerate(filtered):
            is_selected = symbol == self._vm.selectedSymbol
            card = _selectable_grid_card(symbol, is_selected)
            card.setFixedHeight(36)
            card.clicked.connect(lambda s=symbol: self._on_selected(s))
            self._grid.addWidget(card, index // 3, index % 3)

    def _on_selected(self, symbol: str) -> None:
        self._vm.selectedSymbol = symbol
        self.accept()


# ====================================================================== #
# 9. Time Range Picker Modal
# ====================================================================== #


class TimeRangePickerDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("KHOẢNG THỜI GIAN BACKTEST", parent=parent)
        self.setObjectName("timeRangePickerModal")
        self._vm = view_model
        self.resize(440, 330)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(8)
        self.body_layout.addLayout(self._list_layout)

        self._custom_section = QWidget()
        custom_layout = QVBoxLayout(self._custom_section)
        custom_layout.setContentsMargins(0, 8, 0, 0)
        custom_layout.setSpacing(8)
        hint = QLabel("Nhập khoảng ngày tùy chỉnh:")
        hint.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        custom_layout.addWidget(hint)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._start_field = QLineEdit()
        self._start_field.setObjectName("txtBacktestRangeStart")
        self._start_field.setPlaceholderText("Từ yyyy-MM-dd HH:mm")
        self._start_field.setStyleSheet(_FIELD_STYLE)
        self._start_field.textEdited.connect(self._on_start_edited)
        row.addWidget(self._start_field)
        self._end_field = QLineEdit()
        self._end_field.setObjectName("txtBacktestRangeEnd")
        self._end_field.setPlaceholderText("Đến yyyy-MM-dd HH:mm")
        self._end_field.setStyleSheet(_FIELD_STYLE)
        self._end_field.textEdited.connect(self._on_end_edited)
        row.addWidget(self._end_field)
        custom_layout.addLayout(row)

        apply_btn = QPushButton("Áp dụng")
        apply_btn.setFixedSize(100, 32)
        apply_btn.setStyleSheet(
            f"background-color: {_ACCENT}; color: #000000; font-size: 11px; "
            f"font-weight: bold; border-radius: 6px; border: none;"
        )
        apply_btn.clicked.connect(self.accept)
        custom_row = QHBoxLayout()
        custom_row.addStretch(1)
        custom_row.addWidget(apply_btn)
        custom_layout.addLayout(custom_row)

        self.body_layout.addWidget(self._custom_section)

        view_model.timeRangePresetChanged.connect(self._sync)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for option in self._vm.timeRangePresetOptions:
            value = option.get("value", "")
            is_selected = value == self._vm.timeRangePreset
            btn = _selectable_list_card("", option.get("label", value), "", is_selected)
            btn.clicked.connect(lambda _checked=False, v=value: self._on_selected(v))
            self._list_layout.addWidget(btn)

        is_custom = self._vm.timeRangePreset == "custom"
        self._custom_section.setVisible(is_custom)
        if is_custom:
            self._start_field.setText(self._vm.customStartText)
            self._end_field.setText(self._vm.customEndText)
            self.resize(440, 410)
        else:
            self.resize(440, 330)

    def _on_selected(self, value: str) -> None:
        self._vm.timeRangePreset = value
        if value != "custom":
            self.accept()

    def _on_start_edited(self, text: str) -> None:
        self._vm.customStartText = text

    def _on_end_edited(self, text: str) -> None:
        self._vm.customEndText = text


# ====================================================================== #
# 10. Timezone Picker Modal
# ====================================================================== #


class TimezonePickerDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(
            "CHỌN MÚI GIỜ HIỂN THỊ",
            "Chỉ đổi giờ hiển thị. Dữ liệu và Backtest luôn tính theo UTC.",
            parent=parent,
        )
        self.setObjectName("timezonePickerModal")
        self._vm = view_model
        self.resize(440, 350)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._list_layout = QVBoxLayout(content)
        self._list_layout.setSpacing(6)
        scroll.setWidget(content)
        self.body_layout.addWidget(scroll)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for option in self._vm.displayTimezoneOptions:
            tz_id = option.get("id", "")
            is_selected = tz_id == self._vm.displayTimezone
            btn = _selectable_list_card(
                f"tzItem_{tz_id}", option.get("label", tz_id), "", is_selected
            )
            btn.clicked.connect(lambda _checked=False, t=tz_id: self._on_selected(t))
            self._list_layout.addWidget(btn)

    def _on_selected(self, tz_id: str) -> None:
        self._vm.setDisplayTimezone(tz_id)
        self.accept()


# ====================================================================== #
# 11. Strategy Properties Modal (BOT-104) — the biggest one
# ====================================================================== #


class _NumericStepLineEdit(QLineEdit):
    """Port of `BotParamField.qml`'s `Keys.onPressed`/`WheelHandler`: Up/Down
    keys and mouse-wheel scrolls step a numeric field through
    `BackTestViewModel.step_bot_param_value()` (Python-side normalisation —
    the QML original deliberately did NOT reimplement this in JS math)."""

    def __init__(
        self,
        text: str,
        field_name: str,
        view_model: BackTestViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._field_name = field_name
        self._vm = view_model

    def _step(self, direction: int) -> None:
        next_value = self._vm.step_bot_param_value(
            self._field_name, self.text(), direction
        )
        if next_value != self.text():
            self.setText(next_value)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Up:
            self._step(1)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Down:
            self._step(-1)
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:
        if not self.hasFocus():
            event.ignore()
            return
        self._step(1 if event.angleDelta().y() > 0 else -1)
        event.accept()


class _BotParamFieldWidget(QWidget):
    """Port of `BotParamField.qml`: picks a widget purely from
    `field_data["kind"]`, mirroring exactly what the QML `Loader` did."""

    def __init__(
        self,
        field_data: dict,
        view_model: BackTestViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.field_name = field_data.get("name", "")
        self._field_data = field_data
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        suffix = field_data.get("suffix", "")
        label_text = field_data.get("label", "") + (f" ({suffix})" if suffix else "")
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 10px;")
        layout.addWidget(label)

        kind = field_data.get("kind", "string")
        value = field_data.get("value", "")
        self._input: QWidget
        if kind == "bool":
            checkbox = QCheckBox()
            checkbox.setChecked(value is True or value == "true")
            self._input = checkbox
        elif field_data.get("options"):
            combo = QComboBox()
            options = field_data["options"]
            combo.addItems([str(o) for o in options])
            if value in options:
                combo.setCurrentIndex(options.index(value))
            self._input = combo
        elif kind in ("int", "float"):
            field = _NumericStepLineEdit(str(value), self.field_name, view_model)
            minval = field_data.get("minval")
            maxval = field_data.get("maxval")
            if kind == "int":
                field.setValidator(
                    QIntValidator(
                        int(minval) if minval is not None else -999_999_999,
                        int(maxval) if maxval is not None else 999_999_999,
                    )
                )
            else:
                field.setValidator(
                    QDoubleValidator(
                        float(minval) if minval is not None else -999_999_999.0,
                        float(maxval) if maxval is not None else 999_999_999.0,
                        8,
                    )
                )
            self._input = field
        else:
            self._input = QLineEdit(str(value))

        self._input.setObjectName(f"fldBotParam_{self.field_name}")
        self._input.setFixedHeight(32)
        if isinstance(self._input, (QLineEdit, QComboBox)):
            self._input.setStyleSheet(_FIELD_STYLE)
        layout.addWidget(self._input)

    def value(self) -> object:
        if isinstance(self._input, QCheckBox):
            return self._input.isChecked()
        if isinstance(self._input, QComboBox):
            return self._input.currentText()
        return self._input.text()

    def reset_to_default(self) -> None:
        default = self._field_data.get("default")
        if isinstance(self._input, QCheckBox):
            self._input.setChecked(default is True or default == "true")
        elif isinstance(self._input, QComboBox):
            idx = self._input.findText(str(default))
            if idx >= 0:
                self._input.setCurrentIndex(idx)
        else:
            self._input.setText(str(default))


class StrategyPropertiesDialog(Overlay):
    """Port of `StrategyPropertiesModal.qml` (766 lines, BOT-104) — 4-tab
    dialog. Tabs 3/4 ("Định dạng"/"Hiển thị") were themselves QML
    placeholder text ("Sắp ra mắt" — Coming soon), ported as-is, not
    expanded."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("CÀI ĐẶT CHIẾN LƯỢC", parent=parent)
        self.setObjectName("botParamsDialog")
        self._vm = view_model
        self._strategy_name = ""
        self._field_widgets: list[_BotParamFieldWidget] = []
        self.resize(680, 620)

        self._tabs = QTabWidget()
        self.body_layout.addWidget(self._tabs)

        self._inputs_tab = QWidget()
        self._inputs_layout = QVBoxLayout(self._inputs_tab)
        self._inputs_layout.setObjectName("strategyInputsContent")
        self._inputs_layout.setSpacing(14)
        inputs_scroll = QScrollArea()
        inputs_scroll.setWidgetResizable(True)
        inputs_scroll.setFrameShape(QFrame.Shape.NoFrame)
        inputs_scroll.setWidget(self._inputs_tab)
        self._tabs.addTab(inputs_scroll, "Các đầu vào")

        self._properties_tab = self._build_properties_tab()
        properties_scroll = QScrollArea()
        properties_scroll.setWidgetResizable(True)
        properties_scroll.setFrameShape(QFrame.Shape.NoFrame)
        properties_scroll.setWidget(self._properties_tab)
        self._tabs.addTab(properties_scroll, "Đặc tính")

        style_tab = QLabel("Hiển thị và màu sắc chỉ báo chiến lược (Sắp ra mắt)")
        style_tab.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 12px; padding: 12px;"
        )
        self._tabs.addTab(style_tab, "Định dạng")

        visibility_tab = QLabel("Bộ lọc hiển thị theo khung thời gian (Sắp ra mắt)")
        visibility_tab.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 12px; padding: 12px;"
        )
        self._tabs.addTab(visibility_tab, "Hiển thị")

        view_model.botParamsRowsChanged.connect(self._sync_inputs)
        view_model.botParamsSaved.connect(self.accept)

    # -- Tab 2: Properties ------------------------------------------------

    def _build_properties_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("strategyPropertiesContent")
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        layout.addLayout(_section_header("$", "Vốn ban đầu & tiền tệ"))
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        self._prop_initial_capital = QLineEdit()
        self._prop_initial_capital.setObjectName("propInitialCapital")
        row1.addLayout(_field_row("Vốn ban đầu", self._prop_initial_capital), 1)
        self._prop_currency = QComboBox()
        self._prop_currency.setObjectName("propCurrency")
        self._prop_currency.addItems(["USD", "USDT", "BTC", "VND"])
        row1.addLayout(_field_row("Đơn vị tiền tệ", self._prop_currency))
        layout.addLayout(row1)

        layout.addLayout(_section_header("#", "Kích thước lệnh & Pyramiding"))
        row2 = QHBoxLayout()
        row2.setSpacing(12)
        self._prop_order_size_type = QComboBox()
        self._prop_order_size_type.setObjectName("propOrderSizeType")
        self._prop_order_size_type.addItem(
            "% Vốn cổ phần (Equity)", "percent_of_equity"
        )
        self._prop_order_size_type.addItem("USD Cố định (Cash)", "fixed_cash")
        self._prop_order_size_type.addItem("Hợp đồng / Coin", "fixed_contracts")
        row2.addLayout(_field_row("Loại kích thước lệnh", self._prop_order_size_type))
        self._prop_order_size_value = QLineEdit()
        self._prop_order_size_value.setObjectName("propOrderSizeValue")
        row2.addLayout(_field_row("Giá trị kích thước", self._prop_order_size_value), 1)
        self._prop_pyramiding = QSpinBox()
        self._prop_pyramiding.setObjectName("propPyramiding")
        self._prop_pyramiding.setRange(1, 10)
        row2.addLayout(_field_row("Kim tự tháp (Lệnh tối đa)", self._prop_pyramiding))
        layout.addLayout(row2)

        layout.addLayout(_section_header("%", "Hoa hồng & Trượt giá"))
        row3 = QHBoxLayout()
        row3.setSpacing(12)
        self._prop_commission_type = QComboBox()
        self._prop_commission_type.setObjectName("propCommissionType")
        self._prop_commission_type.addItem("% Giá trị lệnh", "percent")
        self._prop_commission_type.addItem("USD / Lệnh", "cash_per_order")
        self._prop_commission_type.addItem("USD / Hợp đồng", "cash_per_contract")
        row3.addLayout(_field_row("Loại hoa hồng", self._prop_commission_type))
        self._prop_commission_value = QLineEdit()
        self._prop_commission_value.setObjectName("propCommissionValue")
        row3.addLayout(_field_row("Mức hoa hồng", self._prop_commission_value), 1)
        self._prop_slippage_ticks = QSpinBox()
        self._prop_slippage_ticks.setObjectName("propSlippageTicks")
        self._prop_slippage_ticks.setRange(0, 100)
        row3.addLayout(_field_row("Trượt giá (Ticks)", self._prop_slippage_ticks))
        layout.addLayout(row3)

        layout.addLayout(_section_header("x", "Đòn bẩy (Leverage)"))
        row4 = QHBoxLayout()
        row4.setSpacing(12)
        self._prop_long_leverage = QSpinBox()
        self._prop_long_leverage.setObjectName("propLongLeverage")
        self._prop_long_leverage.setRange(1, 125)
        row4.addLayout(_field_row("Đòn bẩy Long (x)", self._prop_long_leverage), 1)
        self._prop_short_leverage = QSpinBox()
        self._prop_short_leverage.setObjectName("propShortLeverage")
        self._prop_short_leverage.setRange(1, 125)
        row4.addLayout(_field_row("Đòn bẩy Short (x)", self._prop_short_leverage), 1)
        layout.addLayout(row4)

        layout.addLayout(_section_header("%", "Chốt lời tự động (Take Profit %)"))
        row5 = QHBoxLayout()
        row5.setSpacing(12)
        self._prop_take_profit_enabled = QCheckBox("Bật Take Profit %")
        self._prop_take_profit_enabled.setObjectName("propTakeProfitEnabled")
        self._prop_take_profit_enabled.setStyleSheet(f"color: {Palette.TEXT_PRIMARY};")
        row5.addWidget(self._prop_take_profit_enabled)
        self._prop_take_profit_pct = QLineEdit()
        self._prop_take_profit_pct.setObjectName("propTakeProfitPct")
        self._prop_take_profit_enabled.toggled.connect(
            self._prop_take_profit_pct.setEnabled
        )
        row5.addLayout(
            _field_row(
                "% Chốt lời (khớp take_profit_percent của strategy)",
                self._prop_take_profit_pct,
            ),
            1,
        )
        layout.addLayout(row5)

        layout.addStretch(1)
        return tab

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        btn_reset = QPushButton("Đặt lại mặc định")
        btn_reset.setObjectName("btnResetBotParams")
        btn_reset.clicked.connect(self.reset_all_fields)
        row.addWidget(btn_reset)
        row.addStretch(1)
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setObjectName("btnBotParamsCancel")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)
        btn_save = QPushButton("Lưu & Chạy lại")
        btn_save.setObjectName("btnBotParamsSave")
        btn_save.setStyleSheet(
            f"background-color: {_ACCENT}; color: #000000; font-weight: bold; "
            f"border-radius: 6px; padding: 6px 14px;"
        )
        btn_save.clicked.connect(self.save_and_rerun)
        row.addWidget(btn_save)
        return row

    def open_for_strategy(self, strategy_name: str) -> None:
        self._strategy_name = strategy_name
        self.title = (
            f"CÀI ĐẶT CHIẾN LƯỢC: {strategy_name.upper()}"
            if strategy_name
            else "CÀI ĐẶT CHIẾN LƯỢC"
        )
        self._sync_inputs()
        self._sync_properties()
        self.show()
        self.raise_()

    def _sync_inputs(self) -> None:
        while self._inputs_layout.count():
            item = self._inputs_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._field_widgets = []

        rows = self._vm.botParamsRows
        if not rows:
            empty = QLabel("Chiến lược này không có tham số đầu vào nào để cấu hình.")
            empty.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
            self._inputs_layout.addWidget(empty)
            return

        for row in rows:
            row_type = row.get("rowType", "")
            if row_type == "header":
                self._inputs_layout.addLayout(
                    _section_header("~", row.get("groupLabel", ""))
                )
            elif row_type == "field":
                field_widget = _BotParamFieldWidget(row.get("field", {}), self._vm)
                self._inputs_layout.addWidget(field_widget)
                self._field_widgets.append(field_widget)

    def _sync_properties(self) -> None:
        vm = self._vm
        self._prop_initial_capital.setText(vm.initialCapitalText)
        idx = self._prop_currency.findText(vm.selectedCurrency)
        if idx >= 0:
            self._prop_currency.setCurrentIndex(idx)
        type_idx = {"fixed_cash": 1, "fixed_contracts": 2}.get(vm.orderSizeType, 0)
        self._prop_order_size_type.setCurrentIndex(type_idx)
        self._prop_order_size_value.setText(vm.orderSizeText)
        self._prop_pyramiding.setValue(vm.pyramiding)
        commission_idx = {"cash_per_order": 1, "cash_per_contract": 2}.get(
            vm.commissionType, 0
        )
        self._prop_commission_type.setCurrentIndex(commission_idx)
        self._prop_commission_value.setText(vm.commissionText)
        self._prop_slippage_ticks.setValue(vm.slippageTicks)
        self._prop_long_leverage.setValue(int(vm.longLeverage))
        self._prop_short_leverage.setValue(int(vm.shortLeverage))
        self._prop_take_profit_enabled.setChecked(vm.takeProfitPctEnabled)
        self._prop_take_profit_pct.setText(vm.takeProfitPctText)
        self._prop_take_profit_pct.setEnabled(vm.takeProfitPctEnabled)

    def reset_all_fields(self) -> None:
        for field_widget in self._field_widgets:
            field_widget.reset_to_default()
        self._prop_initial_capital.setText("10000")
        self._prop_currency.setCurrentIndex(0)
        self._prop_order_size_type.setCurrentIndex(0)
        self._prop_order_size_value.setText("100")
        self._prop_pyramiding.setValue(1)
        self._prop_commission_type.setCurrentIndex(0)
        self._prop_commission_value.setText("0.1")
        self._prop_slippage_ticks.setValue(0)
        self._prop_long_leverage.setValue(1)
        self._prop_short_leverage.setValue(1)
        self._prop_take_profit_enabled.setChecked(False)
        self._prop_take_profit_pct.setText("2.0")

    def save_and_rerun(self) -> None:
        input_values = {fw.field_name: fw.value() for fw in self._field_widgets}
        broker_props = {
            "initial_capital": self._prop_initial_capital.text(),
            "currency": self._prop_currency.currentText(),
            "order_size_type": self._prop_order_size_type.currentData(),
            "order_size_text": self._prop_order_size_value.text(),
            "pyramiding": self._prop_pyramiding.value(),
            "commission_type": self._prop_commission_type.currentData(),
            "commission_text": self._prop_commission_value.text(),
            "slippage_ticks": self._prop_slippage_ticks.value(),
            "long_leverage": self._prop_long_leverage.value(),
            "short_leverage": self._prop_short_leverage.value(),
            "take_profit_enabled": self._prop_take_profit_enabled.isChecked(),
            "take_profit_pct_text": self._prop_take_profit_pct.text(),
        }
        self._vm.requestStrategyPropertiesSave(
            {"inputs": input_values, "properties": broker_props}
        )


# ====================================================================== #
# Orchestrator — replaces BackTestModals.qml + OverlayHost
# ====================================================================== #


class BackTestModalsHost:
    """Owns all 11 modal `QDialog`s, built lazily on first open (matching
    every other lazy-modal precedent in this app —
    `DataManagementView._kline_inspector`, EPIC-005E2/E3), and wires
    `BackTestViewModel`'s `openXRequested` signals to them. Replaces both
    `BackTestModals.qml` and Engine's `OverlayHost`/`QQuickWidget` — a real
    `QDialog` is already modal and self-centering over its parent, so the
    full-window click-through overlay QML existed for no longer applies."""

    def __init__(self, view_model: BackTestViewModel, parent: QWidget) -> None:
        self._vm = view_model
        self._parent = parent
        self._capital: CapitalDialogWidget | None = None
        self._extended_metrics: ExtendedMetricsDialog | None = None
        self._limitations: LimitationsDialog | None = None
        self._indicator_picker: IndicatorPickerDialog | None = None
        self._order_execution: OrderExecutionDialog | None = None
        self._strategy_picker: StrategyPickerDialog | None = None
        self._timeframe_picker: TimeframePickerDialog | None = None
        self._symbol_picker: BacktestSymbolPickerDialog | None = None
        self._time_range_picker: TimeRangePickerDialog | None = None
        self._timezone_picker: TimezonePickerDialog | None = None
        self._strategy_properties: StrategyPropertiesDialog | None = None

        view_model.openCapitalRequested.connect(self._open_capital)
        view_model.openExtendedMetricsRequested.connect(self._open_extended_metrics)
        view_model.openLimitationsRequested.connect(self._open_limitations)
        view_model.openIndicatorPickerRequested.connect(self._open_indicator_picker)
        view_model.openOrderExecutionRequested.connect(self._open_order_execution)
        view_model.openStrategyPickerRequested.connect(self._open_strategy_picker)
        view_model.openTimeframePickerRequested.connect(self._open_timeframe_picker)
        view_model.openSymbolPickerRequested.connect(self._open_symbol_picker)
        view_model.openTimeRangePickerRequested.connect(self._open_time_range_picker)
        view_model.openTimezonePickerRequested.connect(self._open_timezone_picker)
        view_model.openBotParamsRequested.connect(self._open_bot_params)

    def _open_capital(self, _x: float, _y: float) -> None:
        if self._capital is None:
            self._capital = CapitalDialogWidget(self._vm, self._parent)
        self._capital.open_dialog()

    def _open_extended_metrics(self) -> None:
        if self._extended_metrics is None:
            self._extended_metrics = ExtendedMetricsDialog(self._vm, self._parent)
        self._extended_metrics.show()
        self._extended_metrics.raise_()

    def _open_limitations(self) -> None:
        if self._limitations is None:
            self._limitations = LimitationsDialog(self._vm, self._parent)
        self._limitations.show()
        self._limitations.raise_()

    def _open_indicator_picker(self, _x: float, _y: float) -> None:
        if self._indicator_picker is None:
            self._indicator_picker = IndicatorPickerDialog(self._vm, self._parent)
        self._indicator_picker.show()
        self._indicator_picker.raise_()

    def _open_order_execution(self, _x: float, _y: float) -> None:
        if self._order_execution is None:
            self._order_execution = OrderExecutionDialog(self._vm, self._parent)
        self._order_execution.show()
        self._order_execution.raise_()

    def _open_strategy_picker(self) -> None:
        if self._strategy_picker is None:
            self._strategy_picker = StrategyPickerDialog(self._vm, self._parent)
        self._strategy_picker.show()
        self._strategy_picker.raise_()

    def _open_timeframe_picker(self) -> None:
        if self._timeframe_picker is None:
            self._timeframe_picker = TimeframePickerDialog(self._vm, self._parent)
        self._timeframe_picker.show()
        self._timeframe_picker.raise_()

    def _open_symbol_picker(self) -> None:
        if self._symbol_picker is None:
            self._symbol_picker = BacktestSymbolPickerDialog(self._vm, self._parent)
        self._symbol_picker.show()
        self._symbol_picker.raise_()

    def _open_time_range_picker(self) -> None:
        if self._time_range_picker is None:
            self._time_range_picker = TimeRangePickerDialog(self._vm, self._parent)
        self._time_range_picker.show()
        self._time_range_picker.raise_()

    def _open_timezone_picker(self) -> None:
        if self._timezone_picker is None:
            self._timezone_picker = TimezonePickerDialog(self._vm, self._parent)
        self._timezone_picker.show()
        self._timezone_picker.raise_()

    def _open_bot_params(self, strategy_name: str) -> None:
        if self._strategy_properties is None:
            self._strategy_properties = StrategyPropertiesDialog(self._vm, self._parent)
        self._strategy_properties.open_for_strategy(strategy_name)
