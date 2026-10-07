"""Unit-tier fixtures: a unit test never reaches the network (`EPIC-030H`).

`ci-rule.md` §2 says the unit tier uses no network. Until this file nothing
enforced it: a unit test that reached a real host passed whenever the host
answered and failed — slowly, and as somebody else's flake — whenever it did
not. The fixture below makes that rule a failure at the call that breaks it.

@details Every `connect()`/`connect_ex()` and every addressed `sendto()`/
`sendmsg()` (UDP) on a `socket.socket` is checked before any packet leaves.
Allowed: `AF_UNIX`, the literal name `localhost`, and any literal IP address
that is loopback (`127.0.0.0/8`, `::1`). Anything else raises
`NetworkAccessBlockedError`. `socket.getaddrinfo` and the legacy `gethostbyname`/`gethostbyname_ex`/
`gethostbyaddr` are guarded too, so a name is
refused before it is resolved — a DNS lookup is itself network access, and
`socket.create_connection`, asyncio, `requests` and `aiohttp` all resolve
through it before they connect.

Socket *creation* and `socket.socketpair()` are left alone: asyncio's event
loop (`asyncio_mode = "auto"`) builds its self-pipe from a socket pair, and a
loopback listener (`tests/unit/fake_exchange/`) is in-process by definition.
`tests/unit/test_unit_tests_never_reach_the_network.py` pins both halves.

Retire when: the unit tier runs in a sandbox with no network interface, so the
operating system refuses the connection on its own.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.tests.unit import network_block


@pytest.fixture(autouse=True)
def _block_non_loopback_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    network_block.install(monkeypatch)
