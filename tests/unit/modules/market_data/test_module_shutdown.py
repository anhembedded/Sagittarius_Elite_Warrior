"""`BUG-122` — shutdown must not build what it only wants to close.

`MarketDataModule.shutdown()` closed the exchange client by resolving
`IExchangeClient` unconditionally. The port is bound lazily, so a session
that never opened a chart had no client — and the `resolve()` **built one**
purely to close it: a network call on the way out (`BUG-045`'s shape), and
`python-binance`'s `Client.__init__` creates an asyncio event loop inside its
websocket helper that nobody then closes, so the interpreter printed an
`Exception ignored in BaseEventLoop.__del__` traceback to stderr on exit.

The wart was known and documented in that method's own docstring, which said
fixing it "needs a way to ask the container whether a singleton was ever
instantiated, which it does not currently offer". The Engine does offer it:
`Registration.instantiated`, whose own docstring says the distinction matters
"when the question is *what has actually been built so far*".
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.module import MarketDataModule
from sagittarius_engine.interfaces.i_container import Registration


class _RecordingContainer:
    """Answers `registrations()` and records every `resolve()`.

    A stand-in for `IContainer`, which is an Engine port owned by nobody —
    the substitution `test_no_foreign_port_is_mocked.py` permits by name.
    """

    def __init__(self, *, client_instantiated: bool) -> None:
        self.resolved: list[type] = []
        self._client_instantiated = client_instantiated
        self.database_manager = SimpleNamespace(dispose_all=lambda: None)
        self.client = SimpleNamespace(closed=False)

    def registrations(self) -> dict[type, Registration]:
        return {
            IExchangeClient: Registration(
                abstract=IExchangeClient,
                concrete=None,
                lifetime="singleton",
                instantiated=self._client_instantiated,
            )
        }

    def resolve(self, abstract: type) -> Any:
        self.resolved.append(abstract)
        if abstract is IExchangeClient:
            return SimpleNamespace(close=self._close)
        return self.database_manager

    def _close(self) -> None:
        self.client.closed = True


def _context(container: _RecordingContainer) -> SimpleNamespace:
    return SimpleNamespace(container=container)


def test_shutdown_does_not_build_a_client_that_was_never_used() -> None:
    """The regression itself: a session that never asked for market data must
    exit without a single exchange call."""
    container = _RecordingContainer(client_instantiated=False)

    MarketDataModule().shutdown(_context(container))

    assert IExchangeClient not in container.resolved, (
        "shutdown resolved IExchangeClient although none was ever built — "
        "that constructs a Binance client, which is a network call and leaks "
        "an asyncio event loop (BUG-122)"
    )


def test_shutdown_still_closes_a_client_that_was_used() -> None:
    """The other half: skipping the close for a client that *is* open would
    leak the socket this method exists to release."""
    container = _RecordingContainer(client_instantiated=True)

    MarketDataModule().shutdown(_context(container))

    assert IExchangeClient in container.resolved
    assert container.client.closed is True


def test_shutdown_always_disposes_the_database_engines() -> None:
    """Unconditional, unlike the client: an undisposed SQLAlchemy engine keeps
    its pool open, which is the `ResourceWarning` the gate greps for."""
    disposed: list[bool] = []
    container = _RecordingContainer(client_instantiated=False)
    container.database_manager = SimpleNamespace(
        dispose_all=lambda: disposed.append(True)
    )

    MarketDataModule().shutdown(_context(container))

    assert disposed == [True]
