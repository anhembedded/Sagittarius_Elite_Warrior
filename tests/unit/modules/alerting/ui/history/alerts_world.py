"""`EPIC-036D2` — the Alerts screen over the real read model, outbox and worker.

Only the channels are scripted (`FakeAlertChannel`); the history, the view and the presenter
are the real ones. The thread manager runs a read as it is submitted, or holds it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from PySide6.QtWidgets import QComboBox, QPushButton
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.registered_channel_catalog import (
    RegisteredChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.outbox_alert_history import (
    OutboxAlertHistory,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_history import (
    IAlertHistory,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history.alerts_presenter import (
    AlertsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history.alerts_view import (
    AlertsView,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.ui.options.alerts_page_world import (
    InlineThreads,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import Rig, build_rig
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


@dataclass
class AlertsScreen:
    presenter: AlertsPresenter
    view: AlertsView
    rig: Rig
    threads: InlineThreads

    def cell(self, row: int, column: str) -> str:
        table = self.view.history_table
        return table.text(row, table.view.model().sourceModel().column(column))

    def choose(self, text: str) -> None:
        box = self.view.findChild(QComboBox, "cmbAlertSeverity")
        box.setCurrentText(text)

    def refresh(self) -> None:
        button = self.view.findChild(QPushButton, "btnRefreshAlerts")
        assert button.isEnabled(), "Refresh is disabled"
        button.click()


def build_screen(
    request: Any,
    tmp_path: Path,
    channel_ids: tuple[str, ...] = ("discord",),
    history: IAlertHistory | None = None,
    services: dict[type, Any] | None = None,
) -> AlertsScreen:
    rig = build_rig(tmp_path, channel_ids)
    threads = InlineThreads()
    the_history = history or OutboxAlertHistory(
        rig.outbox, RegisteredChannelCatalog(rig.channels)
    )
    ports: dict[type, Any] = {
        IAlertHistory: the_history,
        IThreadManager: threads,
        **(services or {}),
    }
    container = Mock()
    container.resolve.side_effect = lambda interface: ports.get(interface, Mock())
    view = AlertsView()
    request.addfinalizer(view.deleteLater)
    presenter = AlertsPresenter(view, container)
    request.addfinalizer(presenter.shutdown)
    return AlertsScreen(presenter, view, rig, threads)
