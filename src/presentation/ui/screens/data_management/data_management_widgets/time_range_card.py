"""The card showing the selected data time range."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.date_range_picker import (
    pick_date_range,
)

from .field_style import field_style


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

    def _on_pick_range(self) -> None:
        chosen = pick_date_range(
            self,
            start_text=self._from_field.text(),
            end_text=self._to_field.text(),
        )
        if chosen is None:
            return
        start, end = chosen
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
