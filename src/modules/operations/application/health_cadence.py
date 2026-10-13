"""How often the host publishes, what state it says, and what happens around a snapshot (`EPIC-038D`).

The snapshot machinery (`HealthPublishing`, scheduled by the module's `boot()`)
exists for every writable copy of the app; it says `SERVING` every ten seconds.
The `run` host changes three things about it and nothing else: the interval
(`--health-interval`), the state (it says `BOOTING`, `DRAINING` and the rest), and
two moments the host cares about - before a snapshot (the probes that measure the
clock skew) and after it (the health line). This object is where the host says so,
before the app boots, and where the module reads it when it does.

It is one small mutable value shared by two parties on purpose: the entry point
configures it while the object graph is being built, the module's `boot()` reads
it, and `RunHost` moves the state. Nothing here knows a bot, a probe or a log line.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HEALTH_INTERVAL_SECONDS,
    HealthSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_health import (
    IHostHealth,
)

type BeforeHook = Callable[[], None]
type AfterHook = Callable[[HealthSnapshot], None]


class HealthCadence:
    def __init__(
        self,
        interval_s: int = HEALTH_INTERVAL_SECONDS,
        state: HostState = HostState.SERVING,
    ) -> None:
        self._lock = threading.Lock()
        self._interval_s = interval_s
        self._state = state
        self._before: list[BeforeHook] = []
        self._after: list[AfterHook] = []
        self._publish: Callable[[], None] | None = None

    @property
    def interval_s(self) -> int:
        return self._interval_s

    @property
    def state(self) -> HostState:
        with self._lock:
            return self._state

    def configure(self, interval_s: int, state: HostState) -> None:
        """Before the app boots: how often to publish and what the first snapshot says."""
        with self._lock:
            self._interval_s = interval_s
            self._state = state

    def set_state(self, state: HostState) -> None:
        with self._lock:
            self._state = state

    def add_before(self, hook: BeforeHook) -> None:
        self._before.append(hook)

    def add_after(self, hook: AfterHook) -> None:
        self._after.append(hook)

    @property
    def before_hooks(self) -> tuple[BeforeHook, ...]:
        return tuple(self._before)

    @property
    def after_hooks(self) -> tuple[AfterHook, ...]:
        return tuple(self._after)

    def attach(self, publish: Callable[[], None]) -> None:
        """The module hands over what writes a snapshot now (`HealthPublishing.tick`)."""
        self._publish = publish

    def publish_now(self) -> None:
        """A snapshot now; nothing when no publishing is attached (a read-only copy)."""
        publish = self._publish
        if publish is not None:
            publish()


class CadenceHostHealth(IHostHealth):
    """The host's view of the cadence: set the state, ask for a snapshot."""

    def __init__(self, cadence: HealthCadence) -> None:
        self._cadence = cadence

    def set_state(self, state: HostState) -> None:
        self._cadence.set_state(state)

    def publish_now(self) -> None:
        self._cadence.publish_now()
