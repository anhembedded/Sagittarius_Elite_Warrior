"""The Quiet hours group of the Alerts page (`EPIC-036D6`): a check box, a From and a To time,
one line saying what is set and Save. Stock controls only.

Save with the box checked keeps the period; Save with it cleared turns quiet hours off, so the
check box is what the group means rather than a second control for the same thing.
"""

from __future__ import annotations

from datetime import time

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import quiet_hours_words
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.quiet_hours_view_model import (
    QuietHoursViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

_TIME_FORMAT = "HH:mm"


def _time_of(edit: QTimeEdit) -> time:
    chosen = edit.time()
    return time(chosen.hour(), chosen.minute())


class QuietHoursGroup(QGroupBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(quiet_hours_words.TITLE, parent)
        layout = QVBoxLayout(self)
        intro = plain_label(quiet_hours_words.INTRO)
        intro.setObjectName("lblQuietHoursIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self._line_label = plain_label()
        self._line_label.setObjectName("lblQuietHoursState")
        self._line_label.setWordWrap(True)
        layout.addWidget(self._line_label)

        self._enable = QCheckBox(quiet_hours_words.ENABLE)
        self._enable.setObjectName("chkQuietHours")
        layout.addWidget(self._enable)
        times = QHBoxLayout()
        self._start = QTimeEdit()
        self._start.setObjectName("timQuietFrom")
        self._start.setDisplayFormat(_TIME_FORMAT)
        self._end = QTimeEdit()
        self._end.setObjectName("timQuietTo")
        self._end.setDisplayFormat(_TIME_FORMAT)
        times.addWidget(plain_label(quiet_hours_words.FROM))
        times.addWidget(self._start)
        times.addWidget(plain_label(quiet_hours_words.TO))
        times.addWidget(self._end)
        times.addStretch(1)
        layout.addLayout(times)
        self._save_button = QPushButton(quiet_hours_words.SAVE)
        self._save_button.setObjectName("btnSaveQuietHours")
        buttons = QHBoxLayout()
        buttons.addWidget(self._save_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self._idle = True
        self._editable = True
        self._enable.toggled.connect(lambda _on: self._apply_enabled())

    def connect_view_model(self, view_model: QuietHoursViewModel) -> None:
        self._save_button.clicked.connect(lambda: self._send_choice(view_model))
        view_model.state_changed.connect(lambda: self._show_state(view_model))
        self._show_state(view_model)

    def set_idle(self, idle: bool) -> None:
        """Nothing is being done: the controls may be used (unless this copy is read-only)."""
        self._idle = idle
        self._apply_enabled()

    def _send_choice(self, view_model: QuietHoursViewModel) -> None:
        if self._enable.isChecked():
            view_model.request_period(_time_of(self._start), _time_of(self._end))
        else:
            view_model.request_turn_off()

    def _show_state(self, view_model: QuietHoursViewModel) -> None:
        self._editable = view_model.editable
        self._enable.setChecked(view_model.enabled)
        self._start.setTime(
            QTime(view_model.from_time.hour, view_model.from_time.minute)
        )
        self._end.setTime(QTime(view_model.to_time.hour, view_model.to_time.minute))
        self._line_label.setText(view_model.line)
        self._apply_enabled()

    def _apply_enabled(self) -> None:
        usable = self._idle and self._editable
        self._enable.setEnabled(usable)
        self._start.setEnabled(usable and self._enable.isChecked())
        self._end.setEnabled(usable and self._enable.isChecked())
        self._save_button.setEnabled(usable)
