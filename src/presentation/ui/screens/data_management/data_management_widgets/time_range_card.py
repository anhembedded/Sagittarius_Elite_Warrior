"""The card showing the selected data time range."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeRangePicker.time_range_picker_dialog import (
    TimeRangePickerDialog,
)

from .field_style import field_style

#: Seed for the "≈ N nến" summary before `set_timeframe_source()` is ever
#: called (a bare `TimeRangeCardWidget()`, as every existing test builds
#: one) — `DataManagementView.set_view_model()` always calls it with the
#: screen's real `selectedInterval`, so this constant is a safety default,
#: not the app's actual behaviour. Derived from `TimeFrame.ONE_MINUTE` rather
#: than hand-computed, so the seconds/label pair cannot drift apart.
_FALLBACK_TIMEFRAME_SECONDS = TimeFrame.ONE_MINUTE.to_seconds()
_FALLBACK_TIMEFRAME_LABEL = TimeFrame.ONE_MINUTE.value


class TimeRangeCardWidget(QWidget):  # base-exempt: a form group, not a card
    """Port of the engine's `TimeRangeCard.qml`: a "use custom time range"
    toggle plus two free-text From/To fields (not QDateTimeEdit — the QML
    version never validated format at the widget level either; the
    presenter's `_parse_datetime`/`SyncCoordinator.parse_datetime` is the
    real validation, unchanged by this migration).

    **Named "Card" but not one**, and deliberately left that way: it is a
    checkbox stacked over two fields with zero margins and no chrome of its
    own. The name is inherited from the QML file it ports. Giving it
    `Panel`'s background and border to match the name would be styling
    driven by a filename."""

    customTimeToggled = Signal(bool)
    fromDateTimeEdited = Signal(str)
    toDateTimeEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._read_only = False
        self._get_timeframe_seconds: Callable[[], int] = lambda: (
            _FALLBACK_TIMEFRAME_SECONDS
        )
        self._get_timeframe_label: Callable[[], str] = lambda: _FALLBACK_TIMEFRAME_LABEL
        self._range_dialog: TimeRangePickerDialog | None = None

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

        # A second way to fill the same two fields, not a replacement for
        # them: the presenter parses what is typed, and a user who prefers
        # typing keeps that.
        pick_row = QHBoxLayout()
        pick_row.setContentsMargins(0, 0, 0, 0)
        pick_row.addStretch(1)
        self._btn_pick_range = QPushButton("Chọn lịch")
        self._btn_pick_range.setObjectName("btnPickDateRange")
        self._btn_pick_range.setFixedHeight(22)
        self._btn_pick_range.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pick_range.setStyleSheet(
            f"QPushButton {{ color: {Palette.ACCENT}; background: transparent; "
            f"border: 0; border-radius: 4px; font-size: 11px; padding: 0 6px; }}"
            f"QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }}"
        )
        self._btn_pick_range.clicked.connect(self._on_pick_range)
        pick_row.addWidget(self._btn_pick_range)
        layout.addLayout(pick_row)

        self._apply_enabled_state()

    def set_timeframe_source(
        self, get_seconds: Callable[[], int], get_label: Callable[[], str]
    ) -> None:
        """Wires the picker's "≈ N nến" summary to the screen's actual
        active timeframe. Called once by `DataManagementView.set_view_model()`
        — this widget holds no ViewModel reference of its own (every other
        setter here is the same push-down shape), so it cannot read
        `selectedInterval` itself."""
        self._get_timeframe_seconds = get_seconds
        self._get_timeframe_label = get_label

    def _on_pick_range(self) -> None:
        if self._range_dialog is None:
            self._range_dialog = TimeRangePickerDialog(
                get_from_text=lambda: self._from_field.text(),
                get_to_text=lambda: self._to_field.text(),
                get_timeframe_seconds=lambda: self._get_timeframe_seconds(),
                get_timeframe_label=lambda: self._get_timeframe_label(),
                parent=self,
            )
            self._range_dialog.applied.connect(self._on_range_applied)
        self._range_dialog.open_dialog()

    def _on_range_applied(self, start: str, end: str) -> None:
        self._from_field.setText(start)
        self._to_field.setText(end)
        # The same signals typing emits — the view model must not be able to
        # tell which of the two ways filled the field.
        self.fromDateTimeEdited.emit(start)
        self.toDateTimeEdited.emit(end)

    def _on_toggled(self, checked: bool) -> None:
        self._apply_enabled_state()
        self.customTimeToggled.emit(checked)

    def _apply_enabled_state(self) -> None:
        fields_enabled = self._toggle.isChecked() and not self._read_only
        self._from_field.setEnabled(fields_enabled)
        self._to_field.setEnabled(fields_enabled)
        self._btn_pick_range.setEnabled(fields_enabled)
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
