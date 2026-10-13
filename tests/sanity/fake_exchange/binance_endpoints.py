"""`BUG-199` — the one place that moves every `python-binance` endpoint.

`python-binance` keeps each API family's base URL as a class attribute of
`BaseClient`, which both `Client` (REST) and `AsyncClient` (REST behind the
websocket service) inherit. The sanity fixture used to override one of them,
`Client.API_URL`, so the only request that reached the fake exchange was a Spot
mainnet read; the Futures mainnet host (`FUTURES_URL`), both testnets
(`API_TESTNET_URL`, `FUTURES_TESTNET_URL`) and everything `AsyncClient` builds
went to the real internet.

So the redirect is by completeness, not by the endpoints a test happens to use:
it walks every URL the installed `BaseClient` declares. The Spot and USD-M
Futures families (and the Spot wallet family) go to the fake exchange; every
other URL goes to a loopback port nothing listens on, where a request fails
at once and is never answered by a real host. A URL a future `python-binance`
adds is covered the day it is added.

Retire when: the sanity tier no longer boots the application with real
`python-binance` clients.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from binance.base_client import BaseClient

from .server import FakeServerUrls

_SPOT_FAMILY = ("API_URL", "API_TESTNET_URL", "API_DEMO_URL")
_FUTURES_FAMILY = ("FUTURES_URL", "FUTURES_TESTNET_URL", "FUTURES_DEMO_URL")
_WALLET_FAMILY = ("MARGIN_API_URL",)

#: Nothing listens on the discard port; a connect to it is refused immediately.
_DEAD_END = "127.0.0.1:9"


def binance_endpoint_names() -> list[str]:
    """Every base-URL attribute the installed `BaseClient` declares."""
    return sorted(
        name
        for name in dir(BaseClient)
        if isinstance(getattr(BaseClient, name), str)
        and "://" in getattr(BaseClient, name)
    )


def _destination(name: str, urls: FakeServerUrls) -> str:
    if name in _SPOT_FAMILY:
        return urls.spot
    if name in _FUTURES_FAMILY:
        return urls.futures
    if name in _WALLET_FAMILY:
        return urls.margin
    scheme = "ws" if getattr(BaseClient, name).startswith("ws") else "http"
    return f"{scheme}://{_DEAD_END}/{name}"


@contextmanager
def binance_clients_pointed_at(urls: FakeServerUrls) -> Iterator[None]:
    """Moves every endpoint of every `Client` and `AsyncClient` built inside the
    block, restoring the library's own on exit. Enter it before the application
    is composed: a client built earlier keeps the host it was built with."""
    with ExitStack() as stack:
        for name in binance_endpoint_names():
            stack.enter_context(
                patch.object(BaseClient, name, _destination(name, urls))
            )
        yield
