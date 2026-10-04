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

_LOCAL_HOSTNAMES = frozenset({"localhost"})


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


def refusal(address: object) -> NetworkAccessBlockedError:
    return NetworkAccessBlockedError(
        f"unit test tried to connect to {address!r}; the unit tier uses no "
        "network (ci-rule.md §2) — use a loopback fake or move the test to "
        "tests/integration/"
    )
