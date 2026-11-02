"""`EPIC-047E` - the VPS tab (UI thread) and Add to VPS (a pool thread) ask for the same link: one session, one supervisor, one stop at quit.

The business promise (module doc of `shared_vps_session.py`): a bot sent from the Bots tab goes over the connection the VPS tab shows,
never over a second one; and whoever starts the link stops it when the application quits, even if the VPS tab was never opened.
"""

from __future__ import annotations

import threading
from typing import Any

from PySide6.QtCore import QCoreApplication
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import LinkProfile
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.shell.vps_tab.quit_hook import stop_at_quit
from Sagittarius_Elite_Warrior.src.shell.vps_tab.shared_vps_session import (
    SharedVpsSession,
)
from Sagittarius_Elite_Warrior.src.shell.vps_tab.vps_tab_session import VpsTabSession
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.link_profiles import (
    LinkProfiles,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.transport_registry import (
    TransportRegistry,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.dispatcher_world import (
    _Local,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.desk.desk_world import PROFILE
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer

#: How long the first caller waits for a second one to overlap it; bounded, and never reached when the lock is there.
_OVERLAP_S = 0.3


class _Notifier(INotifier):
    def notify(self, headline: str, detail: str = "") -> None:
        pass

    def report_failure(self, notice: Any) -> None:
        pass


class _Chosen(LinkProfiles):
    def selected(self) -> LinkProfile | None:
        return PROFILE


def _kinds() -> BotKindCatalog:
    return BotKindCatalog([GridKind(None, GridThresholds())])  # type: ignore[arg-type]


def _in_threads(count: int, work: Any) -> None:
    threads = [threading.Thread(target=work) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)


def test_two_threads_asking_first_get_one_session() -> None:
    container = StdLibContainer()
    slow = threading.Event()

    container.singleton(LinkProfiles, LinkProfiles())
    container.singleton(TransportRegistry, TransportRegistry())
    container.singleton(ICommandDispatcher, _Local())
    container.singleton(IBotKindCatalog, _kinds())
    container.singleton(INotifier, _Notifier())
    shared = SharedVpsSession(container)
    built: list[VpsTabSession] = []
    real_init = VpsTabSession.__init__

    def slow_init(self: VpsTabSession, *args: Any, **kwargs: Any) -> None:
        slow.wait(_OVERLAP_S)  # the window a second caller would use to build its own
        real_init(self, *args, **kwargs)

    VpsTabSession.__init__ = slow_init  # type: ignore[method-assign]
    try:
        _in_threads(2, lambda: built.append(shared.session()))
    finally:
        VpsTabSession.__init__ = real_init  # type: ignore[method-assign]

    assert len(built) == 2
    assert built[0] is built[1]


def test_the_link_is_stopped_at_quit_even_when_the_vps_tab_was_never_opened(
    qtbot, monkeypatch
) -> None:
    stopped: list[bool] = []
    monkeypatch.setattr(VpsTabSession, "stop", lambda self: stopped.append(True))
    container = StdLibContainer()
    container.singleton(LinkProfiles, LinkProfiles())
    container.singleton(TransportRegistry, TransportRegistry())
    container.singleton(ICommandDispatcher, _Local())
    container.singleton(IBotKindCatalog, _kinds())
    container.singleton(INotifier, _Notifier())
    shared = SharedVpsSession(container)  # held as the container holds it
    shared.stop_at_quit_with(stop_at_quit)
    shared.session()

    app = QCoreApplication.instance()
    assert app is not None
    app.aboutToQuit.emit()

    assert stopped == [True]
    assert shared.session() is shared.session()
