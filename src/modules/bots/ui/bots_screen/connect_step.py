"""`EPIC-034D` — the Connect step: a selected bot's venue account is read by
itself, and the answer opens or locks the chart and the Plan (D1, D6).

Owned by the presenter. It owns the step's lifecycle
(`bot_readiness_fsm_matrix.py`), its own fenced reads (a newer read supersedes an
older one, so a late answer for a bot no longer selected is dropped), the
shared snapshots and the re-read timer, and tells the screen through one
signal; `ConnectEffects` applies it. It reads and never trades: the query it
asks goes through `IVenueAccountReader`.

One snapshot per `(venue, symbol)` is shared by every bot on it: selecting a
second bot on the same symbol within `FRESH_SECONDS` reuses the read instead of
asking the exchange again. The timer and Retry always ask again.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_connection import (
    GetVenueConnectionQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
    ReadinessStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessEvent,
    ReadinessState,
    next_state,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_view import (
    ConnectView,
    connected_view,
    connecting_view,
    errored_view,
    failed_view,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    FencedReads,
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOwnershipTracker,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Bots.Connect")

#: A read this young is shared by every bot on the same venue and symbol.
FRESH_SECONDS = 30.0
#: The selected bot's account is read again this often (`EPIC-034D`, D6).
REFRESH_MS = 60_000

type SnapshotKey = tuple[AccountSource, str]


class ConnectStep(QObject):
    """@brief The selected bot's connection to its venue's account."""

    #: The `ConnectView` now to show; emitted at every change of it.
    changed = Signal(object)

    def __init__(
        self,
        threads: IThreadManager,
        dispatcher: ICommandDispatcher,
        now: Callable[[], datetime],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._dispatcher = dispatcher
        self._reads = FencedReads(threads, {ReadKind.CONNECT: ActionOwnershipTracker()})
        self._now = now
        self._state = ReadinessState.NOT_CONNECTED
        self._bot: BotSnapshot | None = None
        self._snapshots: dict[SnapshotKey, VenueAccountSnapshot] = {}
        self.view = ConnectView()
        self.snapshot: VenueAccountSnapshot | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self._on_timer)
        self._reads.answered.connect(self._on_account_read)
        self._reads.failed.connect(self._on_account_failed)

    def select(self, bot: BotSnapshot | None) -> None:
        """Starts the step afresh on `bot`; `None` ends it."""
        self._bot = bot
        if bot is None:
            self._timer.stop()
            self._transition(ReadinessEvent.DESELECTED, ConnectView(), None)
            return
        self._timer.start()
        source = AccountSource.for_venue(bot.venue)
        shared = self._shared(source, bot.symbol)
        if shared is not None:
            logger.debug("Connect %s: %s shares a fresh read", source.value, bot.name)
            self._transition(ReadinessEvent.SELECTED, connecting_view(source), None)
            self._transition(ReadinessEvent.READ_OK, connected_view(shared), shared)
            return
        self._transition(ReadinessEvent.SELECTED, connecting_view(source), None)
        self._ask(bot)

    @property
    def state(self) -> ReadinessState:
        return self._state

    def assessed(self, readiness: BotReadiness | None) -> None:
        """A fresh assessment of the selected bot (`EPIC-034H`): a connected
        bot moves to the state its items name; nothing else is moved by it."""
        if readiness is None:
            return
        steps = {step.step: step for step in readiness.steps}
        if steps[ReadinessStep.DESIGN].items:
            event = ReadinessEvent.DESIGN_OPEN
        elif readiness.items:
            event = ReadinessEvent.RUN_OPEN
        else:
            event = ReadinessEvent.ALL_CLEAR
        self._state = next_state(self._state, event)

    def retry(self) -> None:
        bot = self._bot
        if bot is not None and self._state is not ReadinessState.CONNECTING:
            source = AccountSource.for_venue(bot.venue)
            self._transition(
                ReadinessEvent.RETRY, connecting_view(source), self.snapshot
            )
            self._ask(bot)

    def stop(self) -> None:
        """Answers in flight are dropped and no read is asked again."""
        self._timer.stop()
        self._reads.drop_all()

    # -- answers ----------------------------------------------------------- #

    def _on_account_read(self, _kind: ReadKind, label: str, answer: object) -> None:
        if not self._is_current(label):
            return
        if isinstance(answer, VenueAccountSnapshot):
            self._snapshots[(answer.source, answer.symbol)] = answer
            self._transition(ReadinessEvent.READ_OK, connected_view(answer), answer)
        elif isinstance(answer, ConnectFailure):
            self._forget(answer.source)
            self._transition(ReadinessEvent.READ_FAILED, failed_view(answer), None)
        else:
            raise TypeError(
                f"a connect read answers a snapshot or a failure, not {answer!r}"
            )

    def _on_account_failed(self, _kind: ReadKind, label: str, error: str) -> None:
        bot = self._bot
        if bot is not None and self._is_current(label):
            source = AccountSource.for_venue(bot.venue)
            self._forget(source)
            self._transition(
                ReadinessEvent.READ_FAILED, errored_view(source, error), None
            )

    def _forget(self, source: AccountSource) -> None:
        """A failed read means the account is not reachable now: no earlier
        read of its symbols may be shared as if it were (PR #417 review)."""
        for key in [key for key in self._snapshots if key[0] is source]:
            del self._snapshots[key]

    def _on_timer(self) -> None:
        bot = self._bot
        if bot is None or self._state is ReadinessState.CONNECTING:
            return
        self._state = next_state(self._state, ReadinessEvent.REFRESH)
        if self._state is ReadinessState.CONNECTING:
            self._publish(connecting_view(AccountSource.for_venue(bot.venue)))
        self._ask(bot)

    # -- helpers ----------------------------------------------------------- #

    def _ask(self, bot: BotSnapshot) -> None:
        query = GetVenueConnectionQuery(bot.venue, bot.symbol)
        dispatcher = self._dispatcher
        self._reads.read(
            ReadKind.CONNECT,
            bot.bot_id,
            lambda: dispatcher.dispatch(type(query), query),
        )

    def _is_current(self, label: str) -> bool:
        return self._bot is not None and self._bot.bot_id == label

    def _shared(
        self, source: AccountSource, symbol: str
    ) -> VenueAccountSnapshot | None:
        snapshot = self._snapshots.get((source, symbol))
        if snapshot is None:
            return None
        age = (self._now() - snapshot.read_at).total_seconds()
        return snapshot if 0 <= age < FRESH_SECONDS else None

    def _transition(
        self,
        event: ReadinessEvent,
        view: ConnectView,
        snapshot: VenueAccountSnapshot | None,
    ) -> None:
        self._state = next_state(self._state, event)
        self.snapshot = snapshot
        self._publish(view)

    def _publish(self, view: ConnectView) -> None:
        self.view = view
        self.changed.emit(view)
