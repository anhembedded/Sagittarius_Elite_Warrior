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

import socket
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.tests.unit.network_block import (
    is_local,
    is_local_lookup,
    refusal,
)


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


@pytest.fixture(autouse=True)
def _block_name_lookups_and_datagrams(monkeypatch: pytest.MonkeyPatch) -> None:
    real_getaddrinfo = socket.getaddrinfo
    real_sendto = socket.socket.sendto
    real_sendmsg = socket.socket.sendmsg

    def guarded_getaddrinfo(host: object, *args: Any, **kwargs: Any) -> Any:
        if not is_local_lookup(host):
            raise refusal(host)
        return real_getaddrinfo(host, *args, **kwargs)

    def guarded_sendto(self: socket.socket, data: Any, *args: Any) -> int:
        # sendto(data, address) or sendto(data, flags, address).
        if args and not is_local(self, args[-1]):
            raise refusal(args[-1])
        return real_sendto(self, data, *args)

    def guarded_sendmsg(self: socket.socket, buffers: Any, *args: Any) -> int:
        # sendmsg(buffers[, ancdata[, flags[, address]]]): only the
        # four-argument form names a destination.
        if len(args) == 3 and args[2] is not None and not is_local(self, args[2]):
            raise refusal(args[2])
        return real_sendmsg(self, buffers, *args)

    def guarded_by_name(real: Any) -> Any:
        def lookup(host: object, *args: Any) -> Any:
            if not is_local_lookup(host):
                raise refusal(host)
            return real(host, *args)

        return lookup

    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    for name in ("gethostbyname", "gethostbyname_ex", "gethostbyaddr"):
        monkeypatch.setattr(socket, name, guarded_by_name(getattr(socket, name)))
    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    monkeypatch.setattr(socket.socket, "sendmsg", guarded_sendmsg)
