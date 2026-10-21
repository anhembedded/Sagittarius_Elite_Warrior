"""The Alerts screen's view (`EPIC-036D2`): what was sent, and whether a channel is failing.

- **Top:** one line naming every channel and whether it is working, and a notice bar that
  appears only while a channel is failing.
- **Central:** the history table, with a severity filter and Refresh above it.

Stock controls in a `WorkbenchSurface`, no style sheet. The view shows what the presenter
hands it; the filter is the view's own, since it only narrows what was already read.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.alert_history_report import (
    AlertHistoryRow,
    ChannelHealth,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history import history_words
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history.history_table_model import (
    AlertHistoryTableModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.notice_bar import (
    NoticeBar,
    NoticeKind,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

ALERTS_ROUTE = "alerts"
#: This mode's surface. Declared here because a module may not import `shell/`;
#: `test_the_alerts_view_renders_the_surface_the_shell_declares` holds it equal to
#: `shell/surfaces.py`'s `alerts` entry.
ALERTS_SURFACE = Surface(
    ALERTS_ROUTE, owner="alerting", accepts=frozenset({Place.WORKSPACE})
)


class AlertsView(BaseView):
    """@brief The View of the Alerts screen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("alertsScreen")
        self._history = AlertHistoryTableModel()
        self.history_table = SpecTable(
            self._history,
            object_name="tblAlertHistory",
            empty_text=history_words.EMPTY_TEXT,
        )
        self._channels = plain_label()
        self._channels.setObjectName("lblAlertChannels")
        self._channels.setWordWrap(True)
        self._notice = NoticeBar(NoticeKind.WARNING, "noticeChannelFailing")
        self._notice.hide()
        self._status = plain_label()
        self._status.setObjectName("lblAlertHistoryStatus")
        self._status.setWordWrap(True)
        self._status.hide()
        self.severity_filter = QComboBox()
        self.severity_filter.setObjectName("cmbAlertSeverity")
        for text, _minimum in history_words.FILTER_CHOICES:
            self.severity_filter.addItem(text)
        self.severity_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("btnRefreshAlerts")
        toolbar = QHBoxLayout()
        toolbar.addWidget(plain_label("Show:"))
        toolbar.addWidget(self.severity_filter)
        toolbar.addStretch(1)
        toolbar.addWidget(self.refresh_button)
        central = QWidget()
        column = QVBoxLayout(central)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self._channels)
        column.addWidget(self._notice)
        column.addLayout(toolbar)
        column.addWidget(self.history_table.body, 1)
        column.addWidget(self._status)
        self.surface = WorkbenchSurface(ALERTS_SURFACE)
        self.surface.place_widget(Place.WORKSPACE, central)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.surface)

    @property
    def channels_text(self) -> str:
        return self._channels.text()

    @property
    def notice_text(self) -> str:
        return "" if self._notice.isHidden() else self._notice.text

    @property
    def history_note(self) -> str:
        return "" if self._status.isHidden() else self._status.text()

    @property
    def shown_count(self) -> int:
        return self._history.rowCount()

    def show_alert_history(
        self, rows: Sequence[AlertHistoryRow], channels: Sequence[ChannelHealth]
    ) -> None:
        self._history.take_alerts_read(rows)
        self._channels.setText(history_words.channels_line(channels))
        notice = history_words.failing_notice(channels)
        if notice:
            self._notice.show_notice(NoticeKind.WARNING, notice)
        self._notice.setVisible(bool(notice))

    def show_history_note(self, text: str) -> None:
        self._status.setText(text)
        self._status.setVisible(bool(text))

    def _on_filter_changed(self, index: int) -> None:
        self._history.filter_by(history_words.FILTER_CHOICES[index][1])
