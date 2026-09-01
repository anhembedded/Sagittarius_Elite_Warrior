"""`EPIC-010` D4 — debounced writes, one store, many contributors.

@par The debounce is not hand-written timing logic
Measured (`EPIC-010` design §5.6.6 row 8): `QTimer.setSingleShot(True)`, then
calling `start()` again on every change, *restarts* the countdown rather than
queuing a second firing — three rapid `start()` calls in a row produced
exactly one `timeout`. So this class does bookkeeping (which contributors are
dirty) rather than timing arithmetic.

@par Why one shared timer, not one per contributor
Matches the coalescing behaviour the design's sequence diagram describes:
changing the symbol and then the interval inside the debounce window is one
user action in spirit and becomes one write, covering every contributor that
went dirty in that window — not one write per field.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from PySide6.QtCore import QObject, Qt, QTimer
from Sagittarius_Elite_Warrior.src.presentation.ui.state.i_state_contributor import (
    IStateContributor,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.ports.i_state_store import (
    IStateStore,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import StateScope

logger = logging.getLogger("App.UiState")

#: Long enough to coalesce a burst of related changes (symbol, then interval)
#: into one write; short enough that a normal quit still lands inside the
#: window essentially every time. `teardown()`'s explicit `flush()` is the
#: real safety net regardless — see `flush()`'s own docstring.
_DEFAULT_DEBOUNCE_MS = 800


class UiStateCoordinator(QObject):
    """Restores contributors on demand, and persists them after they settle.

    @details A `QObject` specifically for its `QTimer`: debounce timers must
    live on the Qt main thread (the same class of requirement `BUG-031`
    exists to guard — a cross-thread `QTimer.start()` raises), and parenting
    this to the timer's owner is how that stays true without a manual check.
    """

    def __init__(
        self,
        store: IStateStore,
        *,
        debounce_ms: int = _DEFAULT_DEBOUNCE_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._dirty: dict[StateScope, IStateContributor] = {}
        self._config_bindings: dict[str, list[tuple[StateScope, tuple[str, ...]]]] = {}

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        # BOT-124 — Qt's default `Qt.TimerType.CoarseTimer` is explicitly
        # allowed to round a timer's real deadline UP by ~5% (Qt docs:
        # "try to keep accuracy within 5% of the desired interval") to let
        # the OS coalesce wakeups. `remainingTime()` reflects that rounded
        # deadline, not `debounce_ms` — reproduced under CPU load: right
        # after `start()`, `remainingTime()` read as high as 5250 for a
        # requested 5000ms interval, and `test_marking_again_restarts_...`'s
        # `assert before < debounce_ms` failed (`5036 < 5000`) even after a
        # real 200ms `qtbot.wait()`. `PreciseTimer` drops the coalescing —
        # this is a short UI debounce (hundreds of ms to a few seconds), not
        # a long-lived background poll where coarse batching would matter
        # for battery/wakeup cost.
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._write_dirty_contributors)

    def restore_into(self, contributor: IStateContributor) -> None:
        """Reads `contributor`'s slice and applies it.

        @details Boundary rule 4 (`EPIC-010` design §3.1): this coordinator
        never inspects `data` — it does not know what a valid symbol or
        strategy is. Validation is entirely `restore_state()`'s job.
        """
        data = self._store.read(contributor.state_scope)
        contributor.restore_state(data)

    def mark_dirty(self, contributor: IStateContributor) -> None:
        """Records that `contributor` changed, and (re)starts the debounce window."""
        self._dirty[contributor.state_scope] = contributor
        self._timer.start()

    def discard(self, contributor: IStateContributor) -> None:
        """Drops `contributor`'s remembered state immediately, and cancels any
        pending write for it — a discarded value must not be resurrected by a
        debounce window that was already in flight."""
        self._dirty.pop(contributor.state_scope, None)
        self._store.discard(contributor.state_scope)

    def register_config_binding(
        self, scope: StateScope, config_key: str, state_keys: Iterable[str]
    ) -> None:
        """A contributor declares which of its own remembered fields a
        `IConfig` key outranks (`EPIC-010H`'s `ui_state > user_config`
        precedence).

        @details `EPIC-017A` — inverts who owns this knowledge. Before this,
        `SettingsPresenter` held one hardcoded map of every screen's scope
        key and field names; a new screen that started reading
        `DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL` had to be added there by someone
        editing Settings, not by the screen itself. Now each contributor
        registers its own binding, next to where it already calls
        `restore_into()` — the same "the screen declares itself" shape as
        `state_scope`/`capture_state()`/`restore_state()`.

        Additive only: calling this twice for the same `(scope, config_key)`
        keeps both registrations (both get discarded — harmless, since
        `discard_keys()` is idempotent), it does not overwrite the first one.
        """
        self._config_bindings.setdefault(config_key, []).append(
            (scope, tuple(state_keys))
        )

    def discard_for_config_key(self, config_key: str) -> None:
        """Discards every remembered field bound to `config_key` via
        `register_config_binding()`.

        @details The Settings-side half of `EPIC-017A`'s inversion: Settings
        calls this once per `IConfig` key it just saved, instead of knowing
        which screens/fields that key outranks. A `config_key` nothing
        registered against is a silent no-op — not every `IConfig` key
        outranks remembered state, and Settings should not need a separate
        allowlist to know which ones do.
        """
        for scope, keys in self._config_bindings.get(config_key, ()):
            self.discard_keys(scope, keys)

    def discard_keys(self, scope: StateScope, keys: Iterable[str]) -> None:
        """Forgets specific remembered values without touching the rest.

        @details `EPIC-010H`'s precedence rule: `ui_state` outranks
        `user_config`'s `DEFAULT_*`, so changing one of those in Settings has
        to invalidate the remembered value it now outranks — otherwise the
        user edits Settings and nothing appears to happen. Scoped to the
        affected keys, because dropping a whole slice to change one default
        would discard every unrelated value on that screen.
        """
        self._store.discard_keys(scope, keys)
        self._store.flush()

    def flush(self) -> None:
        """Writes every pending contributor now, synchronously.

        @details The real safety net, not the debounce timer: `teardown()`
        calls this so a quit inside the debounce window is not lost — a
        pending `QTimer` does not fire once the event loop has stopped
        turning. Never raises; a write failure is the store's problem to
        swallow and log (`IStateStore.flush`'s contract), not this
        coordinator's.
        """
        self._timer.stop()
        self._write_dirty_contributors()
        self._store.flush()

    def _write_dirty_contributors(self) -> None:
        pending = list(self._dirty.items())
        self._dirty.clear()
        for scope, contributor in pending:
            self._store.write(scope, contributor.capture_state())
