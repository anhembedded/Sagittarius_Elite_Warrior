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


def test_a_name_lookup_is_refused_before_any_dns_query() -> None:
    with pytest.raises(NetworkAccessBlockedError, match="example.com"):
        socket.getaddrinfo("example.com", 80)


def test_create_connection_to_a_name_is_refused_at_the_lookup() -> None:
    """`socket.create_connection` resolves before it connects; the refusal
    must come from the lookup, so no DNS packet leaves either."""
    with pytest.raises(NetworkAccessBlockedError, match="example.com"):
        socket.create_connection(("example.com", 80), timeout=1)


@pytest.mark.parametrize("host", [None, "localhost", "127.0.0.1", "::1", "192.0.2.1"])
def test_local_and_literal_lookups_still_resolve(host: str | None) -> None:
    assert socket.getaddrinfo(host, 0, type=socket.SOCK_STREAM)


async def test_an_asyncio_connection_to_a_name_is_refused() -> None:
    loop = asyncio.get_running_loop()
    with pytest.raises(NetworkAccessBlockedError, match="example.com"):
        await loop.create_connection(asyncio.Protocol, "example.com", 80)


def test_a_datagram_to_a_non_loopback_address_is_refused() -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock,
        pytest.raises(NetworkAccessBlockedError, match="192.0.2.1"),
    ):
        sock.sendto(b"x", _UNROUTABLE)


def test_a_datagram_with_flags_to_a_non_loopback_address_is_refused() -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock,
        pytest.raises(NetworkAccessBlockedError, match="192.0.2.1"),
    ):
        sock.sendto(b"x", 0, _UNROUTABLE)


def test_an_addressed_sendmsg_to_a_non_loopback_address_is_refused() -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock,
        pytest.raises(NetworkAccessBlockedError, match="192.0.2.1"),
    ):
        sock.sendmsg([b"x"], [], 0, _UNROUTABLE)


def test_a_loopback_datagram_is_delivered() -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver,
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender,
    ):
        receiver.bind(("127.0.0.1", 0))
        sender.sendto(b"ping", receiver.getsockname())
        assert receiver.recv(4) == b"ping"
