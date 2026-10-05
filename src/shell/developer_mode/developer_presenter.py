"""The Developer mode's presenter (`EPIC-033P`).

@details It records the bus while it lives: a `BusEventRecorder` registered
with the Engine, drained onto the view's log by a `QTimer` on the UI thread
four times a second, so a burst of ticks costs one table update, not one per
event (`BUG-042`). The mode exists only under developer mode
(`developer_screen.py`), so a normal run never observes the bus.

It also places the probes the modules contributed, which needs the container
the view does not have; a run with no contribution table (a test container)
places none.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_table import (
    IContributionTable,
)
from sagittarius_engine.exceptions import DependencyResolutionError
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
from sagittarius_engine.interfaces.i_container import IContainer

from .bus_event_recorder import BusEventRecorder
from .developer_view import DeveloperView

logger = logging.getLogger("App.Shell.Developer")

#: How often the log takes what the bus did, in milliseconds.
DRAIN_INTERVAL_MS = 250


class DeveloperPresenter(BasePresenter):
    """@brief Feeds the event log and places the probes."""

    def __init__(
        self,
        view: DeveloperView,
        container: IContainer,
        recorder: BusEventRecorder | None = None,
    ) -> None:
        super().__init__(view, container)
        self._view = view
        self._recorder = recorder or BusEventRecorder()
        table = _contribution_table(container)
        probes = view.place_probes(table, container) if table is not None else 0
        self._timer = QTimer(self)
        self._timer.setInterval(DRAIN_INTERVAL_MS)
        self._timer.timeout.connect(self.drain)
        self._recorder.start()
        self._timer.start()
        logger.info(
            "Developer mode: recording the event bus, drained every %d ms; "
            "%d probe(s) placed.",
            DRAIN_INTERVAL_MS,
            probes,
        )

    def drain(self) -> None:
        """Moves what the bus did since the last drain onto the log."""
        self._view.append_events(self._recorder.drain())
        self._view.show_lost(self._recorder.lost)

    def shutdown(self) -> None:
        self._timer.stop()
        self._recorder.stop()
        logger.info("Developer mode: stopped recording the event bus.")


def build_developer_presenter(view: BaseView, container: IContainer) -> BasePresenter:
    """The presenter factory the screen contribution names."""
    if not isinstance(view, DeveloperView):
        raise TypeError(
            f"the Developer mode's presenter was handed a {type(view).__name__}, "
            "not a DeveloperView"
        )
    return DeveloperPresenter(view, container)


def _contribution_table(container: IContainer) -> IContributionTable | None:
    """The table, or `None` when this run has none: a container nothing bound
    it in, or a `Mock` one (the smoke tests that build every route)."""
    try:
        table = container.resolve(IContributionTable)
    except DependencyResolutionError:
        return None
    return table if isinstance(table, IContributionTable) else None
