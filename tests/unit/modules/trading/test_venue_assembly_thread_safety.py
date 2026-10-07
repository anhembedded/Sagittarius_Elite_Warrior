"""`EPIC-028A` review F1 — a `VenueAssembly` part is built once even when two
threads ask for it first.

@details `functools.cached_property` stopped locking in Python 3.12. The
container's singletons hide that for the single-venue doors, but
`IVenueContexts.get(venue)` reaches the parts directly, and a second
`FuturesUserDataStream` would open a second socket on one account. The
constructor below blocks its first caller until a second caller has entered
it (bounded wait, no sleep): unlocked, both get in and two caches exist;
locked, the second waits behind the first and reuses its result.
"""

from __future__ import annotations

import threading
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition import venue_assembly
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_assembly import (
    SharedVenueInputs,
    VenueAssembly,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore

_SECOND_CALLER_WAIT_SECONDS = 0.5


def test_two_threads_asking_first_share_one_metadata_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built: list[object] = []
    entered = threading.Event()
    second_arrived = threading.Event()
    lock = threading.Lock()

    def slow_cache_factory() -> object:
        with lock:
            first = not entered.is_set()
            entered.set()
        if first:
            second_arrived.wait(timeout=_SECOND_CALLER_WAIT_SECONDS)
        else:
            second_arrived.set()
        cache = object()
        built.append(cache)
        return cache

    monkeypatch.setattr(
        venue_assembly, "InMemorySymbolOrderMetadataCache", slow_cache_factory
    )
    assembly = VenueAssembly(
        TradingVenue.FUTURES_TESTNET,
        SharedVenueInputs(
            container=Mock(),
            secrets_file_path="unused",
            session_states=VenueSessionStates(),
            secret_store=InMemorySecretStore(),
        ),
    )
    seen: list[object] = []
    threads = [
        threading.Thread(target=lambda: seen.append(assembly.metadata_cache))
        for _ in range(2)
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(built) == 1
    assert seen[0] is seen[1]
