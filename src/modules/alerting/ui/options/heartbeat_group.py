"""The "Heartbeat" group of the Alerts page (`EPIC-036D9`): one combo with the intervals the owner
may choose. Stock controls only. A choice acts at once, like the page's other buttons."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import heartbeat_words
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.heartbeat_view_model import (
    HeartbeatViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label


class HeartbeatGroup(QGroupBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(heartbeat_words.TITLE, parent)
        layout = QVBoxLayout(self)
        intro = plain_label(heartbeat_words.intro())
        intro.setObjectName("lblHeartbeatIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self._box = QComboBox()
        self._box.setObjectName("cmbHeartbeatEvery")
        form.addRow(plain_label(heartbeat_words.FIELD), self._box)
        layout.addLayout(form)
        self._note = plain_label()
        self._note.setObjectName("lblHeartbeatNote")
        self._note.setWordWrap(True)
        layout.addWidget(self._note)
        self._offered: tuple[int, ...] = ()
        self._idle = True
        self._editable = True

    def connect_view_model(self, view_model: HeartbeatViewModel) -> None:
        self._box.activated.connect(
            lambda _index: view_model.request_hours(int(self._box.currentData()))
        )
        view_model.state_changed.connect(lambda: self._show_state(view_model))
        self._show_state(view_model)

    def set_idle(self, idle: bool) -> None:
        """Nothing is being done: the choice may be used (unless this copy is read-only)."""
        self._idle = idle
        self._apply_enabled()

    def _show_state(self, view_model: HeartbeatViewModel) -> None:
        if view_model.offered_hours != self._offered:
            self._offered = view_model.offered_hours
            self._box.clear()
            for hours in self._offered:
                self._box.addItem(heartbeat_words.choice_text(hours), hours)
        self._box.setCurrentIndex(self._box.findData(view_model.hours))
        self._editable = view_model.editable
        self._note.setText(view_model.note)
        self._note.setVisible(bool(view_model.note))
        self._apply_enabled()

    def _apply_enabled(self) -> None:
        self._box.setEnabled(self._idle and self._editable)
