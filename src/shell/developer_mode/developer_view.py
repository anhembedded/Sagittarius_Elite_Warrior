"""The Developer mode's view (`EPIC-033P`), laid out as HLD §11.2.1 lists it.

- **Central:** the event log, a table from its column specs: each emit on the
  bus and each handler that raised, newest at the bottom.
- **Right:** the probes the modules contribute (`Place.DEV_PROBE`), one dock
  each; the presenter places them, since it has the container that builds them.

Stock controls in a `WorkbenchSurface`, no style sheet. The view shows what the
presenter hands it and keeps the newest row in sight while the person has not
scrolled up to read.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_table import (
    IContributionTable,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.shell.surfaces import (
    DEVELOPER_SURFACE_ID,
    surfaces_by_id,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.surface_building import (
    fill_surface,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView
from sagittarius_engine.interfaces.i_container import IContainer

from .bus_event_recorder import BusEventRecord
from .event_log_table_model import EventLogTableModel

EMPTY_LOG_TEXT = "Nothing has been published on the event bus since this mode opened."


def lost_text(lost: int) -> str:
    """What the log says when it fell behind a burst."""
    noun = "event was" if lost == 1 else "events were"
    return (
        f"{lost} {noun} not logged: the bus published faster than the log "
        "could show. The newest are kept."
    )


class DeveloperView(BaseView):
    """@brief The View of the Developer mode."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("developerMode")
        self._log = EventLogTableModel()
        self.event_log = SpecTable(
            self._log,
            object_name="tblEventLog",
            empty_text=EMPTY_LOG_TEXT,
        )
        self._lost = QLabel()
        self._lost.setObjectName("lblEventLogLost")
        self._lost.setWordWrap(True)
        self._lost.hide()
        central = QWidget()
        column = QVBoxLayout(central)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self.event_log.body, 1)
        column.addWidget(self._lost)
        self.surface = WorkbenchSurface(surfaces_by_id()[DEVELOPER_SURFACE_ID])
        self.surface.place_widget(Place.WORKSPACE, central)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.surface)

    @property
    def lost_text(self) -> str:
        return self._lost.text() if not self._lost.isHidden() else ""

    def place_probes(
        self, contributions: IContributionTable, container: IContainer
    ) -> int:
        """Docks every probe contributed to this mode; how many were placed."""
        return fill_surface(self.surface, contributions, container)

    def append_events(self, records: Sequence[BusEventRecord]) -> None:
        if not records:
            return
        bar = self.event_log.view.verticalScrollBar()
        following = bar.value() == bar.maximum()
        self._log.append(records)
        if following:
            self.event_log.view.scrollToBottom()

    def show_lost(self, lost: int) -> None:
        self._lost.setText(lost_text(lost))
        self._lost.setVisible(lost > 0)
