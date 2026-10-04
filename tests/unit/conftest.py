"""Unit-tier fixtures: a unit test never reaches the network (`EPIC-030H`).

`ci-rule.md` §2 says the unit tier uses no network. Until this file nothing
enforced it: a unit test that reached a real host passed whenever the host
answered and failed — slowly, and as somebody else's flake — whenever it did
not. The fixture below makes that rule a failure at the call that breaks it.

@details Every `connect()`/`connect_ex()` on a `socket.socket` is checked
before any packet leaves. Allowed: `AF_UNIX`, the literal name `localhost`,
and any literal IP address that is loopback (`127.0.0.0/8`, `::1`). Anything
else raises `NetworkAccessBlockedError`. Hostnames are never resolved — a DNS
lookup is itself network access, so `example.com` is refused by name.

Socket *creation* and `socket.socketpair()` are left alone: asyncio's event
loop (`asyncio_mode = "auto"`) builds its self-pipe from a socket pair, and a
loopback listener (`tests/unit/fake_exchange/`) is in-process by definition.
`tests/unit/test_unit_tests_never_reach_the_network.py` pins both halves.

Retire when: the unit tier runs in a sandbox with no network interface, so the
operating system refuses the connection on its own.
"""

from __future__ import annotations

import socket

import pytest
from Sagittarius_Elite_Warrior.tests.unit.network_block import is_local, refusal


@pytest.fixture(autouse=True)
def _block_non_loopback_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guarded_connect(self: socket.socket, address: object) -> None:
        if not is_local(self, address):
            raise refusal(address)
        real_connect(self, address)

    def guarded_connect_ex(self: socket.socket, address: object) -> int:
        if not is_local(self, address):
            raise refusal(address)
        return real_connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
