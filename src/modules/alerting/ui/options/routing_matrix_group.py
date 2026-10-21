"""The "Who hears what" group of the Alerts page (`EPIC-036D7`): one row per kind of alert, one
column per running channel, a combo in each cell (Default, Loud, Silent, Off). Stock controls
only. A choice acts at once, like the page's other buttons."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import routing_words
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.routing_matrix_view_model import (
    RoutingMatrixViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label


class RoutingMatrixGroup(QGroupBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(routing_words.TITLE, parent)
        layout = QVBoxLayout(self)
        intro = plain_label(routing_words.INTRO)
        intro.setObjectName("lblRoutingIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self._grid = QGridLayout()
        layout.addLayout(self._grid)
        cover = plain_label(routing_words.COVER_NOTE)
        cover.setObjectName("lblRoutingCover")
        cover.setWordWrap(True)
        layout.addWidget(cover)
        self._note = plain_label()
        self._note.setObjectName("lblRoutingNote")
        self._note.setWordWrap(True)
        layout.addWidget(self._note)
        self._boxes: dict[tuple[str, str], QComboBox] = {}
        self._channels: tuple[str, ...] = ()
        self._idle = True
        self._editable = True

    def connect_view_model(self, view_model: RoutingMatrixViewModel) -> None:
        view_model.state_changed.connect(lambda: self._show_state(view_model))
        self._show_state(view_model)

    def set_idle(self, idle: bool) -> None:
        """Nothing is being done: the cells may be used (unless this copy is read-only)."""
        self._idle = idle
        self._apply_enabled()

    def _show_state(self, view_model: RoutingMatrixViewModel) -> None:
        if view_model.channels != self._channels:
            self._rebuild(view_model)
        for (group_value, channel_id), box in self._boxes.items():
            box.setCurrentIndex(
                box.findData(view_model.cell_value(AlertGroup(group_value), channel_id))
            )
        self._editable = view_model.editable
        self._note.setText(view_model.note)
        self._note.setVisible(bool(view_model.note))
        self._apply_enabled()

    def _rebuild(self, view_model: RoutingMatrixViewModel) -> None:
        while (item := self._grid.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._boxes = {}
        self._channels = view_model.channels
        for column, channel_id in enumerate(self._channels, start=1):
            self._grid.addWidget(
                plain_label(routing_words.channel_title(channel_id)), 0, column
            )
        for row, (group, name, examples) in enumerate(
            routing_words.GROUP_ROWS, start=1
        ):
            label = plain_label(name)
            label.setToolTip(examples)
            self._grid.addWidget(label, row, 0)
            for column, channel_id in enumerate(self._channels, start=1):
                box = QComboBox()
                box.setObjectName(f"cmbRoute_{group.value}_{channel_id}")
                for value, text in routing_words.CHOICES:
                    box.addItem(text, value)
                box.activated.connect(
                    lambda _i, b=box, g=group.value, c=channel_id: (
                        view_model.request_cell(g, c, str(b.currentData()))
                    )
                )
                self._boxes[(group.value, channel_id)] = box
                self._grid.addWidget(box, row, column)

    def _apply_enabled(self) -> None:
        usable = self._idle and self._editable
        for box in self._boxes.values():
            box.setEnabled(usable)
