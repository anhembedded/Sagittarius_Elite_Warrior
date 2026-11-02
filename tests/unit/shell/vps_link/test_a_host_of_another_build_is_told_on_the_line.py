"""`EPIC-047E` (acceptance: version difference) - a host of another build refuses the link, and the tab's line says so in words.

The business promise: when the VPS host runs another build than this desktop, nothing is read or sent; the line above the tab
reads "the VPS host runs build X, this desktop runs Y: run `sudo sew-update`" and the link is not retried (it would be refused again).
The handshake itself is 047D's (`test_link_handshake.py`); this proves the words reach the tab's own line over the real bridge.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import LinkProtocol
from Sagittarius_Elite_Warrior.src.shell.vps_link.host_state_line import (
    host_state_line,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.link_host_world import LinkHostWorld
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_status import (
    LinkState,
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
from Sagittarius_Elite_Warrior.src.support.wire.link_handshake import Hello
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import (
    BOUND_S,
    QUICK,
    VpsHost,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import ROOTS
from Sagittarius_Elite_Warrior.tests.unit.support.wire.desk.desk_world import (
    DESK_HELLO,
    BridgeTransport,
)


class _Status(ILinkObserver):
    def __init__(self) -> None:
        self.failed = threading.Event()
        self.last = LinkStatus(LinkState.IDLE, "")
        self.linked_up = False

    def on_status(self, status: LinkStatus) -> None:
        self.last = status
        if status.state is LinkState.FAILED:
            self.failed.set()

    def on_link_up(self, link: DeskLink, epoch: ConnectionEpoch) -> None:
        self.linked_up = True

    def on_event(self, epoch: ConnectionEpoch, event: dict[str, object]) -> None:
        pass


def test_a_host_of_another_build_is_refused_and_the_line_says_what_to_run() -> None:
    host = VpsHost()
    other = Hello(DESK_HELLO.protocol, "0.0.1", dict(DESK_HELLO.root_hashes))
    registry = TransportRegistry()
    registry.register(
        LinkProtocol.SSH, lambda: BridgeTransport(host, bridge_hello=other)
    )
    watch = _Status()
    supervisor = LinkSupervisor(QUICK, registry, DESK_HELLO, watch)
    supervisor.start()
    try:
        assert watch.failed.wait(BOUND_S), "the refusal never reached the status"
    finally:
        supervisor.stop()
        supervisor.join(BOUND_S)

    line = host_state_line(
        "nathan-warrior",
        LinkHostWorld(ROOTS, _Silent()).current(),
        watch.last,
        datetime.now(UTC),
    )

    assert "the VPS host runs build 0.0.1" in line.text
    assert "run `sudo sew-update`" in line.text
    assert not line.ok
    assert not watch.linked_up
    assert host.bots.asked == 0


class _Silent:
    """A world listener that hears nothing: no snapshot ever arrived."""

    def on_bot_changed(self, bot_id: str, removed: bool) -> None:
        pass

    def on_market(self, market: object) -> None:
        pass

    def on_file_changed(self, kind: str) -> None:
        pass
