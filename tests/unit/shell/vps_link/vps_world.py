"""`EPIC-047E` - what the VPS tab's tests share: a host behind the real `BridgeSession`, a supervised link to it, the world and the control.

The bridge is not imitated: the desktop side is the real `LinkSupervisor`, `LinkHostWorld` and `LinkHostControl`, the host
side is the real `BridgeSession` over the fake ports of `bridge_world`, so a change to either end's wire form fails here.
Nothing in this file reaches an exchange: that is what the AC10 runtime test relies on.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import replace

from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    LinkProtocol,
    ReconnectPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.operations.composition.wire_roots import (
    HOST_READS_DOCUMENT_ROOT,
    MARKET_DATA_DOCUMENT_ROOT,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.link_host_control import (
    LinkHostControl,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.link_host_world import (
    IHostWorldListener,
    LinkHostWorld,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_session import (
    SessionPorts,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_status import (
    LinkStatus,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.desk_link import DeskLink
from Sagittarius_Elite_Warrior.src.support.wire.desk.link_supervisor import (
    ConnectionEpoch,
    ILinkObserver,
    LinkSupervisor,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.transport_registry import (
    TransportRegistry,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import (
    ROOTS,
    FakeCandles,
    FakeDocument,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_operations import (
    full_host_reads,
    full_market_data,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.desk.desk_world import (
    DESK_HELLO,
    PROFILE,
    BridgeHost,
    BridgeTransport,
)

BOUND_S = 5.0
QUICK = replace(PROFILE, reconnect=ReconnectPolicy(first_delay_s=0.0, max_delay_s=0.0))


class VpsHost(BridgeHost):
    """A host that also publishes the market and the reads files."""

    def __init__(self) -> None:
        super().__init__()
        self.market = FakeDocument(MARKET_DATA_DOCUMENT_ROOT, full_market_data())
        self.reads = FakeDocument(HOST_READS_DOCUMENT_ROOT, full_host_reads())
        #: The host's candle store; `None` until a test seeds one (the bridge then answers `no_candles`).
        self.candles: FakeCandles | None = None

    def ports(self) -> SessionPorts:
        return SessionPorts(
            self.bots,
            self.facts,
            self.door,
            {"market": self.market, "reads": self.reads},
            self.candles,
        )


class _Transports:
    def __init__(self, host: VpsHost) -> None:
        self.host = host
        self.made: list[BridgeTransport] = []

    def registry(self) -> TransportRegistry:
        registry = TransportRegistry()
        registry.register(LinkProtocol.SSH, self._next)
        return registry

    def _next(self) -> BridgeTransport:
        transport = BridgeTransport(self.host)
        self.made.append(transport)
        return transport


class _Watch(ILinkObserver, IHostWorldListener):
    """Hands every observer call to the world and signals the test on the named moments."""

    def __init__(self) -> None:
        self.world: LinkHostWorld | None = None
        self.up = threading.Semaphore(0)
        self.bot_changed = threading.Semaphore(0)
        self.market = threading.Semaphore(0)
        self.down = threading.Semaphore(0)
        self.changed: list[tuple[str, bool]] = []

    def on_status(self, status: LinkStatus) -> None:
        assert self.world is not None
        self.world.on_status(status)
        if status.state.value != "connected":
            self.down.release()

    def on_link_up(self, link: DeskLink, epoch: ConnectionEpoch) -> None:
        assert self.world is not None
        self.world.on_link_up(link, epoch)
        self.up.release()

    def on_event(self, epoch: ConnectionEpoch, event: dict[str, object]) -> None:
        assert self.world is not None
        self.world.on_event(epoch, event)

    def on_bot_changed(self, bot_id: str, removed: bool) -> None:
        self.changed.append((bot_id, removed))
        self.bot_changed.release()

    def on_market(self, market: object) -> None:
        self.market.release()


class VpsTabWorld:
    """A running link to a `VpsHost`: the world, the control, and what the tests wait on."""

    def __init__(
        self, host: VpsHost | None = None, *, hold_after_cut: bool = False
    ) -> None:
        """`hold_after_cut` makes the supervisor wait a minute before it redials, so a test can read the
        disconnected picture without racing the reconnect; `stop` ends the wait."""
        profile = (
            replace(
                PROFILE, reconnect=ReconnectPolicy(first_delay_s=60.0, max_delay_s=60.0)
            )
            if hold_after_cut
            else QUICK
        )
        self.host = host or VpsHost()
        self._transports = _Transports(self.host)
        self._watch = _Watch()
        self.world = LinkHostWorld(ROOTS, self._watch)
        self._watch.world = self.world
        self.control = LinkHostControl(self.world, ROOTS)
        self.supervisor = LinkSupervisor(
            profile, self._transports.registry(), DESK_HELLO, self._watch
        )

    def start(self) -> VpsTabWorld:
        self.supervisor.start()
        self.wait_up()
        # The statuses before the welcome (connecting) are not "the link went down".
        while self._watch.down.acquire(blocking=False):
            pass
        return self

    def wait_up(self) -> None:
        assert self._watch.up.acquire(timeout=BOUND_S), "the link did not come up"

    def wait_bot_changed(self) -> None:
        assert self._watch.bot_changed.acquire(timeout=BOUND_S), "no bot event came"

    def wait_down(self) -> None:
        assert self._watch.down.acquire(timeout=BOUND_S), "the link did not go down"

    def cut(self) -> None:
        self._transports.made[-1].cut()

    def stop(self) -> None:
        self.supervisor.stop()
        self.supervisor.join(BOUND_S)

    @property
    def changed(self) -> list[tuple[str, bool]]:
        return self._watch.changed


def started(stop_with: Callable[[Callable[[], None]], None]) -> VpsTabWorld:
    """A running world that `stop_with` (a fixture's finalizer) stops."""
    built = VpsTabWorld().start()
    stop_with(built.stop)
    return built
