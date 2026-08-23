"""QtWidgets building blocks for DatabaseScreen (EPIC-005E), each a direct port of
one QML component this screen used: `TimeRangeCard`, `LogPanel`, `AppProgressBar`
(all from the engine kit or `components/`), and the `SymbolPickerModal`/
`ModalDialogCard` confirm-dialog pattern. Kept in their own module so
`data_management_view.py` stays about assembly, not primitive construction.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QModelIndex, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)


def field_style(extra_height: int | None = None) -> str:
    """QSS matching `FieldBackground.qml`: STATE_IDLE_BG fill, BORDER outline,
    6px radius. `extra_height` overrides the default 32px min-height (the
    search box uses 26px, matching `FieldBackground { implicitHeight: 26 }`)."""
    height = extra_height if extra_height is not None else 32
    return (
        f"background-color: {Palette.STATE_IDLE_BG}; color: {Palette.TEXT_PRIMARY}; "
        f"border: 1px solid {Palette.BORDER}; border-radius: 6px; "
        f"min-height: {height}px; padding: 0 6px;"
    )


class TimeRangeCardWidget(QWidget):
    """Port of the engine's `TimeRangeCard.qml`: a "use custom time range"
    toggle plus two free-text From/To fields (not QDateTimeEdit — the QML
    version never validated format at the widget level either; the
    presenter's `_parse_datetime`/`SyncCoordinator.parse_datetime` is the
    real validation, unchanged by this migration)."""

    customTimeToggled = Signal(bool)
    fromDateTimeEdited = Signal(str)
    toDateTimeEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._read_only = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._toggle = QCheckBox("Use Custom Time Range")
        self._toggle.setStyleSheet(f"color: {Palette.TEXT_PRIMARY};")
        self._toggle.toggled.connect(self._on_toggled)
        layout.addWidget(self._toggle)

        self._from_field = QLineEdit()
        self._from_field.setObjectName("txtFromDateTime")
        self._from_field.setPlaceholderText("From  yyyy-MM-dd HH:mm")
        self._from_field.setStyleSheet(field_style())
        self._from_field.textEdited.connect(self.fromDateTimeEdited)
        layout.addWidget(self._from_field)

        self._to_field = QLineEdit()
        self._to_field.setObjectName("txtToDateTime")
        self._to_field.setPlaceholderText("To  yyyy-MM-dd HH:mm")
        self._to_field.setStyleSheet(field_style())
        self._to_field.textEdited.connect(self.toDateTimeEdited)
        layout.addWidget(self._to_field)

        self._apply_enabled_state()

    def _on_toggled(self, checked: bool) -> None:
        self._apply_enabled_state()
        self.customTimeToggled.emit(checked)

    def _apply_enabled_state(self) -> None:
        fields_enabled = self._toggle.isChecked() and not self._read_only
        self._from_field.setEnabled(fields_enabled)
        self._to_field.setEnabled(fields_enabled)
        self._toggle.setEnabled(not self._read_only)

    def set_use_custom_time(self, value: bool) -> None:
        self._toggle.blockSignals(True)
        self._toggle.setChecked(value)
        self._toggle.blockSignals(False)
        self._apply_enabled_state()

    def set_read_only(self, value: bool) -> None:
        self._read_only = value
        self._apply_enabled_state()

    def set_from_date_time(self, value: str) -> None:
        if self._from_field.text() != value:
            self._from_field.setText(value)

    def set_to_date_time(self, value: str) -> None:
        if self._to_field.text() != value:
            self._to_field.setText(value)


class _LogDelegate(QStyledItemDelegate):
    """Paints one log line as `[HH:MM:SS] message`, coloring the message by
    level — matches LogPanel.qml's delegate (timestamp always muted, message
    danger-colored on error)."""

    def paint(self, painter, option, index) -> None:
        painter.save()
        model = index.model()
        timestamp = model.data(index, model.TimestampRole) or ""
        message = model.data(index, model.MessageRole) or ""
        level = model.data(index, model.LevelRole) or "info"

        rect = option.rect.adjusted(4, 2, -4, -2)
        painter.setPen(Qt.GlobalColor.gray)
        ts_text = f"[{timestamp}]"
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft, ts_text)

        ts_width = painter.fontMetrics().horizontalAdvance(ts_text) + 8
        message_rect = rect.adjusted(ts_width, 0, 0, 0)
        color = Qt.GlobalColor.red if level == "error" else Qt.GlobalColor.white
        painter.setPen(color)
        painter.drawText(
            message_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
            str(message),
        )
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 20)


class LogPanelWidget(QWidget):
    """Port of the engine's `LogPanel.qml`: header (title + live count badge
    + Copy/Clear) over a scrolling line list. Binds `logModel` (a
    `LogListModel`, unchanged) directly as a `QListView` model — the model's
    own `rowsInserted`/`modelReset`/`countChanged` signals drive the view,
    same as QML's ListView did, no Python-side polling."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._log_model = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setStyleSheet(
            f"background-color: {Palette.BG_CARD}; border: 1px solid {Palette.BORDER}; "
            f"border-radius: 8px;"
        )

        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet(
            f"background-color: {Palette.BG_CARD_HEADER}; "
            f"border-top-left-radius: 8px; border-top-right-radius: 8px; "
            f"border-bottom: 1px solid {Palette.BORDER};"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        header_layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {Palette.ACCENT}; font-size: 12px; font-weight: bold;"
        )
        header_layout.addWidget(title_label)

        self._count_label = QLabel("0 EVENTS")
        self._count_label.setObjectName("lblLogCount")
        self._count_label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 9px; font-weight: bold; "
            f"background-color: {Palette.STATE_IDLE_BG}; border: 1px solid {Palette.BORDER}; "
            f"border-radius: 3px; padding: 2px 6px;"
        )
        header_layout.addWidget(self._count_label)
        header_layout.addStretch()

        copy_button = QPushButton("Copy")
        copy_button.setObjectName("btnCopyLog")
        copy_button.setIcon(
            get_icon_loader().get_icon("copy", Palette.TEXT_PRIMARY, 12)
        )
        copy_button.clicked.connect(self._copy_all)
        header_layout.addWidget(copy_button)

        clear_button = QPushButton("Clear")
        clear_button.setObjectName("btnClearLog")
        clear_button.setIcon(
            get_icon_loader().get_icon("trash-2", Palette.TEXT_PRIMARY, 12)
        )
        clear_button.clicked.connect(self._clear)
        header_layout.addWidget(clear_button)

        layout.addWidget(header)

        self._list_view = QListView()
        self._list_view.setObjectName("logList")
        self._list_view.setItemDelegate(_LogDelegate(self._list_view))
        self._list_view.setStyleSheet(
            f"background-color: transparent; border: none; color: {Palette.TEXT_PRIMARY};"
        )
        self._list_view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self._list_view, 1)

    def set_log_model(self, model) -> None:
        self._log_model = model
        self._list_view.setModel(model)
        model.countChanged.connect(self._update_count)
        self._update_count()

    def _update_count(self) -> None:
        count = self._log_model.rowCount(QModelIndex()) if self._log_model else 0
        self._count_label.setText(f"{count} EVENTS")

    def _copy_all(self) -> None:
        if self._log_model is not None:
            self._log_model.copyAllToClipboard()

    def _clear(self) -> None:
        if self._log_model is not None:
            self._log_model.clear()


class AppProgressBarWidget(QWidget):
    """Port of `components/AppProgressBar.qml`: a status-text label over a
    QProgressBar. `indeterminate` maps to Qt's own busy mode
    (`setRange(0, 0)`), which already animates — no custom shimmer needed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._status_label = QLabel()
        self._status_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        layout.addWidget(self._status_label)

        self._bar = QProgressBar()
        self._bar.setObjectName("progressBar")
        self._bar.setTextVisible(True)
        self._bar.setFixedHeight(10)
        self._bar.setStyleSheet(
            f"QProgressBar {{ background-color: #171922; border: 1px solid #2a2d3d; "
            f"border-radius: 3px; color: {Palette.ACCENT}; font-size: 10px; }} "
            f"QProgressBar::chunk {{ background-color: {Palette.ACCENT}; border-radius: 3px; }}"
        )
        layout.addWidget(self._bar)

    def set_status_text(self, text: str) -> None:
        self._status_label.setText(text)
        self._status_label.setVisible(bool(text))

    def set_range(self, minimum: int, maximum: int) -> None:
        self._bar.setRange(minimum, maximum)

    def set_value(self, value: int) -> None:
        self._bar.setValue(value)

    def set_indeterminate(self, indeterminate: bool) -> None:
        if indeterminate:
            self._bar.setRange(0, 0)
        # A determinate range is set separately via set_range(); avoid
        # clobbering it here with a default (0, 100).


class SymbolPickerDialog(QDialog):
    """Port of `SymbolPickerModal.qml`: search field + a grid of symbol
    buttons. `on_symbol_chosen` mirrors the QML version's direct
    `viewModel.selectedSymbol = modelData` write on click."""

    def __init__(
        self,
        get_options: Callable[[], list[str]],
        on_symbol_chosen: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("symbolPickerModal")
        self.setWindowTitle("CHỌN SYMBOL")
        self.setModal(True)
        self.resize(420, 320)
        self.setStyleSheet(
            f"background-color: {Palette.BG_CARD}; color: {Palette.TEXT_PRIMARY};"
        )
        self._get_options = get_options
        self._on_symbol_chosen = on_symbol_chosen

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("CHỌN SYMBOL")
        title.setStyleSheet(
            f"color: {Palette.TEXT_PRIMARY}; font-size: 12px; font-weight: bold;"
        )
        layout.addWidget(title)

        self._search_field = QLineEdit()
        self._search_field.setObjectName("txtSymbolSearch")
        self._search_field.setPlaceholderText("Tìm symbol (vd: BTC)")
        self._search_field.setStyleSheet(field_style())
        self._search_field.textChanged.connect(self._rebuild_grid)
        layout.addWidget(self._search_field)

        self._empty_label = QLabel("Đang tải danh sách symbol từ sàn...")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 12px;")
        layout.addWidget(self._empty_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        self._grid_host = QWidget()
        self._grid_layout = QGridLayout(self._grid_host)
        self._grid_layout.setSpacing(8)
        scroll.setWidget(self._grid_host)
        layout.addWidget(scroll, 1)
        self._scroll = scroll

        self._rebuild_grid()

    def showEvent(self, event) -> None:
        self._rebuild_grid()
        super().showEvent(event)

    def _rebuild_grid(self) -> None:
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        options = self._get_options()
        has_options = bool(options)
        self._empty_label.setVisible(not has_options)
        self._search_field.setVisible(has_options)
        self._scroll.setVisible(has_options)

        needle = self._search_field.text().strip().upper()
        filtered = [s for s in options if not needle or needle in s]

        columns = 3
        for i, symbol in enumerate(filtered):
            button = QPushButton(symbol)
            button.setFixedHeight(36)
            button.setStyleSheet(
                f"QPushButton {{ background-color: #141620; color: {Palette.TEXT_PRIMARY}; "
                f"border: 1px solid {Palette.BORDER}; border-radius: 8px; font-size: 11px; }} "
                f"QPushButton:hover {{ background-color: #1b1d28; }}"
            )
            button.clicked.connect(lambda _checked, s=symbol: self._choose(s))
            self._grid_layout.addWidget(button, i // columns, i % columns)

    def _choose(self, symbol: str) -> None:
        self._on_symbol_chosen(symbol)
        self.close()


class ConfirmDialog(QDialog):
    """Port of the Clear/Purge `ModalDialogCard` confirm dialogs: icon-less
    header (title + subtitle), a message body, Cancel + a danger-styled
    confirm button. Parameterized rather than duplicated once per dialog —
    the QML versions were two near-identical copies of the same shape."""

    def __init__(
        self,
        title: str,
        subtitle: str,
        message: str,
        confirm_text: str,
        confirm_object_name: str,
        on_confirm: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.resize(420, 220)
        self.setStyleSheet(
            f"background-color: {Palette.BG_CARD}; color: {Palette.TEXT_PRIMARY};"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {Palette.DANGER}; font-size: 13px; font-weight: bold;"
        )
        layout.addWidget(title_label)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        layout.addWidget(subtitle_label)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 13px;")
        layout.addWidget(message_label, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        cancel_button = QPushButton("Hủy bỏ")
        cancel_button.clicked.connect(self.close)
        button_row.addWidget(cancel_button)

        confirm_button = QPushButton(confirm_text)
        confirm_button.setObjectName(confirm_object_name)
        confirm_button.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.DANGER}; color: white; "
            f"font-weight: bold; border-radius: 6px; min-height: 34px; }}"
        )

        def _confirm() -> None:
            self.close()
            on_confirm()

        confirm_button.clicked.connect(_confirm)
        button_row.addWidget(confirm_button)

        layout.addLayout(button_row)
