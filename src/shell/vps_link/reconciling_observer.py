"""`EPIC-047E` (AC6) — the link's observer that, after each welcomed link, settles the commands the last one lost.

@details It is the world (`LinkHostWorld`) to the supervisor, plus one thing: once the world has taken the snapshot of a new
connection, a short-lived thread asks the host what it recorded for every command in the ledger (`CommandReconciler`), a few
times while the host has recorded nothing yet. The thread is a daemon: the application's end does not wait for it, and a lost
link ends it (the next link-up starts it again). Nothing is sent to the host that changes anything.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.shell.vps_link.command_reconciler import (
    CommandReconciler,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.unanswered_ledger import (
    UnansweredLedger,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_status import (
    LinkStatus,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.desk_link import DeskLink
from Sagittarius_Elite_Warrior.src.support.wire.desk.link_supervisor import (
    ConnectionEpoch,
    ILinkObserver,
)

#: How many times the host is asked while it has recorded nothing yet, and the pause between asks.
PASSES = 4
PAUSE_S = 5.0


def start_daemon(work: Callable[[], None]) -> None:
    threading.Thread(target=work, name="vps-reconcile", daemon=True).start()


class ReconcilingObserver(ILinkObserver):
    def __init__(
        self,
        inner: ILinkObserver,
        ledger: UnansweredLedger,
        reconciler: CommandReconciler,
        spawn: Callable[[Callable[[], None]], None] = start_daemon,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._inner = inner
        self._ledger = ledger
        self._reconciler = reconciler
        self._spawn = spawn
        self._sleep = sleep

    def on_status(self, status: LinkStatus) -> None:
        self._inner.on_status(status)

    def on_link_up(self, link: DeskLink, epoch: ConnectionEpoch) -> None:
        self._inner.on_link_up(link, epoch)
        if self._ledger.entries():
            self._spawn(self._run)

    def on_event(self, epoch: ConnectionEpoch, event: dict[str, object]) -> None:
        self._inner.on_event(epoch, event)

    def _run(self) -> None:
        for attempt in range(PASSES):
            if self._reconciler.reconcile() == 0:
                return
            if attempt + 1 < PASSES:
                self._sleep(PAUSE_S)
