"""The Alerts screen's view (`EPIC-036D2`): what was sent, and whether a channel is failing.

- **Top:** one line naming every channel and whether it is working, and a notice bar that
  appears only while a channel is failing.
- **Central:** the history table, with a severity filter and Refresh above it.

Stock controls in a `WorkbenchSurface`, no style sheet. The view shows what the presenter
hands it; the filter is the view's own, since it only narrows what was already read.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
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
    """@brief The View of the Alerts screen, and the status-bar indicator it offers
    (`IStatusSource`, `EPIC-036D3`)."""

    #: The owner clicked the indicator: show this mode.
    indicator_clicked = Signal()

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
        self._indicator = QToolButton()
        self._indicator.setObjectName("btnAlertsIndicator")
        self._indicator.setAutoRaise(True)
        self._indicator.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._indicator.setToolTip(history_words.INDICATOR_TIP)
        self._indicator.clicked.connect(self.indicator_clicked)
        self._indicator.hide()
        self.severity_filter = QComboBox()
        self.severity_filter.setObjectName("cmbAlertSeverity")
        for text, _minimum in history_words.FILTER_CHOICES:
            self.severity_filter.addItem(text)
        self.severity_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("btnRefreshAlerts")
        self.retry_button = QPushButton("Retry failed")
        self.retry_button.setObjectName("btnRetryFailed")
        self.retry_button.setToolTip(history_words.RETRY_TIP)
        toolbar = QHBoxLayout()
        toolbar.addWidget(plain_label("Show:"))
        toolbar.addWidget(self.severity_filter)
        toolbar.addStretch(1)
        toolbar.addWidget(self.retry_button)
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
        self.show_channel_health(channels)

    def show_channel_health(self, channels: Sequence[ChannelHealth]) -> None:
        """Only the channels' state: the line, the notice and the indicator. The list stays as it
        was, which is what a read made for the indicator alone brings."""
        self._channels.setText(history_words.channels_line(channels))
        notice = history_words.failing_notice(channels)
        if notice:
            self._notice.show_notice(NoticeKind.WARNING, notice)
        self._notice.setVisible(bool(notice))
        self._indicator.setText(history_words.indicator_text(channels))
        failing = any(channel.failing for channel in channels)
        self._indicator.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
            if failing
            else QIcon()
        )
        self._indicator.setToolTip(history_words.INDICATOR_TIP)
        self._indicator.show()

    def show_health_unknown(self, error_type: str) -> None:
        """The last read failed, so what the indicator said is no longer known: it says so, in
        words, rather than keep an `ok` nobody has checked."""
        self._indicator.setText(history_words.INDICATOR_UNKNOWN)
        self._indicator.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion)
        )
        self._indicator.setToolTip(
            history_words.INDICATOR_UNKNOWN_TIP.format(error_type=error_type)
        )
        self._indicator.show()

    @property
    def indicator_text(self) -> str:
        return self._indicator.text()

    def status_widgets(self) -> Sequence[QWidget]:
        """The indicator, for the window's status bar (`IStatusSource`)."""
        return (self._indicator,)

    def show_history_note(self, text: str) -> None:
        self._status.setText(text)
        self._status.setVisible(bool(text))

    def _on_filter_changed(self, index: int) -> None:
        self._history.filter_by(history_words.FILTER_CHOICES[index][1])
