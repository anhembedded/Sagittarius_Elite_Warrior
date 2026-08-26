"""`UiStateCoordinator` — debounce, restore, discard, flush."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.in_memory_state_store import (
    InMemoryStateStore,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import StateScope
from Sagittarius_Elite_Warrior.src.presentation.ui.state.ui_state_coordinator import (
    UiStateCoordinator,
)


class _FakeContributor:
    """The simplest possible `IStateContributor` — a Protocol needs no base
    class, so this satisfies it structurally, the same way a real presenter
    or `MainWindow` would."""

    def __init__(self, key: str, value: str = "initial") -> None:
        self.state_scope = StateScope(key=key)
        self.value = value
        self.captured_count = 0
        self.restored_with: dict | None = None

    def capture_state(self) -> dict:
        self.captured_count += 1
        return {"value": self.value}

    def restore_state(self, data: dict) -> None:
        self.restored_with = dict(data)


def test_restore_into_reads_the_store_and_applies_it():
    store = InMemoryStateStore()
    store.write(StateScope(key="dashboard"), {"value": "BTCUSDT"})
    coordinator = UiStateCoordinator(store)
    contributor = _FakeContributor("dashboard")

    coordinator.restore_into(contributor)

    assert contributor.restored_with == {"value": "BTCUSDT"}


def test_restore_into_with_no_prior_state_hands_over_an_empty_mapping():
    store = InMemoryStateStore()
    coordinator = UiStateCoordinator(store)
    contributor = _FakeContributor("dashboard")

    coordinator.restore_into(contributor)

    assert contributor.restored_with == {}


def test_flush_writes_every_dirty_contributor(qapp):
    store = InMemoryStateStore()
    coordinator = UiStateCoordinator(
        store, debounce_ms=50_000
    )  # never fires on its own
    a = _FakeContributor("dashboard", value="BTC")
    b = _FakeContributor("backtest", value="ema_pullback")

    coordinator.mark_dirty(a)
    coordinator.mark_dirty(b)
    coordinator.flush()

    assert store.read(a.state_scope) == {"value": "BTC"}
    assert store.read(b.state_scope) == {"value": "ema_pullback"}


def test_debounce_coalesces_a_burst_into_one_write(qtbot):
    """Measured behaviour this relies on: `QTimer.start()` on an active
    single-shot timer restarts the countdown rather than queuing a second
    firing — see the module docstring.

    A burst with NO delay between `mark_dirty()` calls cannot tell "restart"
    apart from "queue, ignore later starts": both produce exactly one write,
    because the dirty-tracking dict is keyed by scope and capture happens
    lazily at flush time, reading whatever the contributor's *current* value
    is — so a queued-but-not-restarted timer firing later still reads the
    final value. The two behaviours only diverge in *when* the write lands,
    which only shows up if a mark can land while a window is already running.
    Real waits between marks (each shorter than the window, their sum longer)
    make that divergence observable: a queuing timer fires mid-burst and
    produces a SECOND write once the trailing mark restarts it from
    inactive, while a genuinely restarting timer produces exactly one.
    """
    debounce_ms = 150
    store = InMemoryStateStore()
    coordinator = UiStateCoordinator(store, debounce_ms=debounce_ms)
    contributor = _FakeContributor("dashboard", value="BTC")

    coordinator.mark_dirty(contributor)
    qtbot.wait(debounce_ms // 2)
    contributor.value = "ETH"
    coordinator.mark_dirty(contributor)
    qtbot.wait(debounce_ms // 2)
    contributor.value = "SOL"
    coordinator.mark_dirty(contributor)  # lands debounce_ms after the first mark

    qtbot.wait(debounce_ms * 3)  # generously past even a queued-timer's 2nd firing

    assert contributor.captured_count == 1
    assert store.read(contributor.state_scope) == {"value": "SOL"}


def test_discard_cancels_a_pending_write_for_that_contributor(qtbot):
    store = InMemoryStateStore()
    store.write(StateScope(key="dashboard"), {"value": "stale-from-last-session"})
    coordinator = UiStateCoordinator(store, debounce_ms=40)
    contributor = _FakeContributor("dashboard", value="BTC")

    coordinator.mark_dirty(contributor)  # queues a write
    coordinator.discard(contributor)  # must cancel it AND clear prior state

    qtbot.wait(200)

    assert store.read(contributor.state_scope) == {}
    assert contributor.captured_count == 0  # the queued write never ran


def test_flush_stops_a_pending_timer_so_the_write_happens_exactly_once(qtbot):
    """`flush()` is the real safety net for a quit inside the debounce window
    — `teardown()` calls it. It must not race a timer that was about to fire
    on its own and produce a duplicate write."""
    store = InMemoryStateStore()
    coordinator = UiStateCoordinator(store, debounce_ms=40)
    contributor = _FakeContributor("dashboard", value="BTC")

    coordinator.mark_dirty(contributor)
    coordinator.flush()
    qtbot.wait(200)  # if the original timer also fired, captured_count would show it

    assert contributor.captured_count == 1
