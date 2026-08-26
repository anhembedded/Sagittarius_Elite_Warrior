"""`NullStateStore` — the optional-dependency fallback and the Sanity-tier store."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.null_state_store import (
    NullStateStore,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import StateScope


def test_read_is_always_empty():
    store = NullStateStore()

    assert store.read(StateScope(key="dashboard")) == {}


def test_write_is_a_no_op_and_does_not_surface_in_a_later_read():
    store = NullStateStore()
    scope = StateScope(key="dashboard")

    store.write(scope, {"symbol": "BTCUSDT"})

    assert store.read(scope) == {}


def test_discard_and_flush_are_harmless():
    store = NullStateStore()
    store.discard(StateScope(key="dashboard"))  # must not raise
    store.flush()  # must not raise
