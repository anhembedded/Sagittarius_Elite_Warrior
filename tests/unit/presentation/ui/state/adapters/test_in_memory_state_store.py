"""`InMemoryStateStore` — the session store, and the test double."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.in_memory_state_store import (
    InMemoryStateStore,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import StateScope


def test_round_trips_a_slice():
    store = InMemoryStateStore()
    scope = StateScope(key="dashboard")

    store.write(scope, {"symbol": "BTCUSDT"})

    assert store.read(scope) == {"symbol": "BTCUSDT"}


def test_missing_scope_reads_as_empty():
    store = InMemoryStateStore()

    assert store.read(StateScope(key="dashboard")) == {}


def test_discard_forgets_the_slice():
    store = InMemoryStateStore()
    scope = StateScope(key="dashboard")
    store.write(scope, {"symbol": "BTCUSDT"})

    store.discard(scope)

    assert store.read(scope) == {}


def test_two_instances_stay_isolated():
    store = InMemoryStateStore()
    a = StateScope(key="dashboard", instance_id="tab-a")
    b = StateScope(key="dashboard", instance_id="tab-b")

    store.write(a, {"symbol": "BTC"})
    store.write(b, {"symbol": "ETH"})

    assert store.read(a) == {"symbol": "BTC"}
    assert store.read(b) == {"symbol": "ETH"}


def test_flush_is_a_harmless_no_op():
    InMemoryStateStore().flush()  # must not raise
