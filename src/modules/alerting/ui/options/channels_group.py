"""The "Channels" group of the Alerts page (`EPIC-036D8`): a check box per running channel, ticked
while the channel is on. Stock controls only. A switch acts at once, like the page's buttons."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QGroupBox, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import (
    channels_words,
    routing_words,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.channels_view_model import (
    ChannelsViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label


class ChannelsGroup(QGroupBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(channels_words.TITLE, parent)
        layout = QVBoxLayout(self)
        intro = plain_label(channels_words.INTRO)
        intro.setObjectName("lblChannelsIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self._boxes_layout = QVBoxLayout()
        layout.addLayout(self._boxes_layout)
        self._note = plain_label()
        self._note.setObjectName("lblChannelsNote")
        self._note.setWordWrap(True)
        layout.addWidget(self._note)
        self._boxes: dict[str, QCheckBox] = {}
        self._channels: tuple[str, ...] = ()
        self._idle = True
        self._editable = True

    def connect_view_model(self, view_model: ChannelsViewModel) -> None:
        view_model.state_changed.connect(lambda: self._show_state(view_model))
        self._show_state(view_model)

    def set_idle(self, idle: bool) -> None:
        """Nothing is being done: the boxes may be used (unless this copy is read-only)."""
        self._idle = idle
        self._apply_enabled()

    def _show_state(self, view_model: ChannelsViewModel) -> None:
        if view_model.channels != self._channels:
            self._rebuild(view_model)
        for channel_id, box in self._boxes.items():
            box.setChecked(view_model.is_on(channel_id))
        self._editable = view_model.editable
        self._note.setText(view_model.note)
        self._note.setVisible(bool(view_model.note))
        self._apply_enabled()

    def _rebuild(self, view_model: ChannelsViewModel) -> None:
        while (item := self._boxes_layout.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._boxes = {}
        self._channels = view_model.channels
        for channel_id in self._channels:
            box = QCheckBox(routing_words.channel_title(channel_id))
            box.setObjectName(f"chkChannel_{channel_id}")
            box.clicked.connect(
                lambda checked, c=channel_id: view_model.request_switch(c, checked)
            )
            self._boxes[channel_id] = box
            self._boxes_layout.addWidget(box)

    def _apply_enabled(self) -> None:
        usable = self._idle and self._editable
        for box in self._boxes.values():
            box.setEnabled(usable)
