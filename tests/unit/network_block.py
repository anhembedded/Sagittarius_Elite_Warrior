"""The unit tier's network block: which addresses a unit test may connect to.

Lives outside `conftest.py` so the exception has one importable identity:
pytest imports a `conftest.py` under a rootdir-relative name, so a test that
imported `NetworkAccessBlockedError` from it would get a different class from
the one the fixture raises. `tests/unit/conftest.py` explains the policy.

Retire when: `tests/unit/conftest.py`'s network block is retired.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any

import pytest

_LOCAL_HOSTNAMES = frozenset({"localhost"})
_PROXY_VARIABLES = tuple(
    variable
    for name in ("http", "https", "all", "ftp")
    for variable in (f"{name}_proxy", f"{name.upper()}_PROXY")
)


class NetworkAccessBlockedError(RuntimeError):
    """A unit test tried to open a connection to a non-loopback address."""


def is_local(sock: socket.socket, address: object) -> bool:
    if getattr(socket, "AF_UNIX", None) is not None and sock.family == socket.AF_UNIX:
        return True
    if not isinstance(address, tuple) or not address:
        return False
    host = address[0]
    if not isinstance(host, str):
        return False
    if host.lower() in _LOCAL_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        # Not a literal IP: a hostname, which we refuse rather than resolve.
        return False


def is_local_lookup(host: object) -> bool:
    """Whether `getaddrinfo(host, ...)` stays on this machine.

    A literal IP address (any, not only loopback) or `None` is parsed, never
    looked up, so it sends no packet; a later `connect()`/`sendto()` to it is
    still checked by `is_local`. `localhost` resolves from the hosts file. Any
    other name would be a DNS query, which is network access.
    """
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not isinstance(host, str):
        return False
    if host.lower() in _LOCAL_HOSTNAMES:
        return True
    try:
        ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    return True


def refusal(address: object) -> NetworkAccessBlockedError:
    return NetworkAccessBlockedError(
        f"unit test tried to connect to {address!r}; the unit tier uses no "
        "network (ci-rule.md §2) — use a loopback fake or move the test to "
        "tests/integration/"
    )


def install(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Refuses every non-loopback connect, datagram and name lookup until the
    test's `monkeypatch` undoes it; see `tests/unit/conftest.py` for the policy.
    Answers the list every refused destination is appended to.

    One definition for every tier that uses it (`BUG-182`): the unit tier and
    the UI integration tier, whose booted app has real adapters behind the
    ports a test does not substitute.
    """
    refused: list[str] = []

    def refuse(address: object) -> NetworkAccessBlockedError:
        refused.append(repr(address))
        return refusal(address)

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo
    real_sendto = socket.socket.sendto
    real_sendmsg = socket.socket.sendmsg

    def guarded_connect(self: socket.socket, address: object) -> None:
        if not is_local(self, address):
            raise refuse(address)
        real_connect(self, address)

    def guarded_connect_ex(self: socket.socket, address: object) -> int:
        if not is_local(self, address):
            raise refuse(address)
        return real_connect_ex(self, address)

    def guarded_getaddrinfo(host: object, *args: Any, **kwargs: Any) -> Any:
        if not is_local_lookup(host):
            raise refuse(host)
        return real_getaddrinfo(host, *args, **kwargs)

    def guarded_sendto(self: socket.socket, data: Any, *args: Any) -> int:
        # sendto(data, address) or sendto(data, flags, address).
        if args and not is_local(self, args[-1]):
            raise refuse(args[-1])
        return real_sendto(self, data, *args)

    def guarded_sendmsg(self: socket.socket, buffers: Any, *args: Any) -> int:
        # sendmsg(buffers[, ancdata[, flags[, address]]]): only the
        # four-argument form names a destination.
        if len(args) == 3 and args[2] is not None and not is_local(self, args[2]):
            raise refuse(args[2])
        return real_sendmsg(self, buffers, *args)

    def guarded_by_name(real: Any) -> Any:
        def lookup(host: object, *args: Any) -> Any:
            if not is_local_lookup(host):
                raise refuse(host)
            return real(host, *args)

        return lookup

    # A forward proxy on loopback (a sandbox's, a developer's) would pass the
    # loopback check and carry the request out: send it direct, to be refused.
    for variable in _PROXY_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    for name in ("gethostbyname", "gethostbyname_ex", "gethostbyaddr"):
        monkeypatch.setattr(socket, name, guarded_by_name(getattr(socket, name)))
    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    monkeypatch.setattr(socket.socket, "sendmsg", guarded_sendmsg)
    return refused
