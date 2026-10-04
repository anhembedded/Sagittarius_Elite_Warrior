"""`EPIC-030H` — the unit tier's network block refuses the world and keeps loopback.

Pins both halves of `tests/unit/conftest.py`'s autouse fixture: a connection
to a non-loopback address fails before any packet is sent, and the in-process
plumbing the unit tier legitimately uses — a loopback listener, a socket pair,
an asyncio loop — keeps working.

Retire when: `tests/unit/conftest.py`'s network block is retired.
"""

from __future__ import annotations

import asyncio
import socket

import pytest
from Sagittarius_Elite_Warrior.tests.unit.network_block import NetworkAccessBlockedError

#: TEST-NET-1 (RFC 5737): documentation-only, never routed. Port 9 is discard.
_UNROUTABLE = ("192.0.2.1", 9)


def test_connect_to_a_non_loopback_address_is_refused() -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
        pytest.raises(NetworkAccessBlockedError, match="192.0.2.1"),
    ):
        sock.connect(_UNROUTABLE)


def test_connect_ex_to_a_non_loopback_address_is_refused() -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
        pytest.raises(NetworkAccessBlockedError, match="192.0.2.1"),
    ):
        sock.connect_ex(_UNROUTABLE)


def test_a_hostname_is_refused_without_being_resolved() -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
        pytest.raises(NetworkAccessBlockedError, match="example.com"),
    ):
        sock.connect(("example.com", 80))


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_a_loopback_listener_accepts_a_connection(host: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.connect((host, port))
            accepted, _ = listener.accept()
            with accepted:
                client.sendall(b"ping")
                assert accepted.recv(4) == b"ping"


def test_a_socketpair_still_works() -> None:
    left, right = socket.socketpair()
    with left, right:
        left.sendall(b"x")
        assert right.recv(1) == b"x"


async def test_an_asyncio_loop_still_runs() -> None:
    """The loop's self-pipe is a socket pair; `asyncio_mode = "auto"` runs this."""
    assert await asyncio.sleep(0, result="done") == "done"
