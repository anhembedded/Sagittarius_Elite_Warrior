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


def test_a_burst_of_marks_produces_exactly_one_write(qtbot):
    """The user-visible half of the debounce: changing the symbol and then the
    interval is one action in spirit and must cost one write.

    Deterministic by construction, not by timing luck — a `QTimer` can only
    fire from the event loop, and these three `mark_dirty()` calls are
    consecutive statements with no chance for it to turn, so no scheduling
    delay can slip a write in between them.
    """
    debounce_ms = 120
    store = InMemoryStateStore()
    coordinator = UiStateCoordinator(store, debounce_ms=debounce_ms)
    contributor = _FakeContributor("dashboard", value="BTC")

    coordinator.mark_dirty(contributor)
    contributor.value = "ETH"
    coordinator.mark_dirty(contributor)
    contributor.value = "SOL"
    coordinator.mark_dirty(contributor)

    qtbot.wait(debounce_ms * 5)

    assert contributor.captured_count == 1
    assert store.read(contributor.state_scope) == {"value": "SOL"}


def test_marking_again_restarts_the_window_instead_of_letting_it_run_out(qtbot):
    """The mechanism the coalescing above rests on: `QTimer.start()` on an
    already-active single-shot timer restarts the countdown rather than
    leaving the original deadline in place (design §5.6.6 row 8).

    @par Why this asserts on `remainingTime()` rather than counting writes
    An earlier version of this test raced the wall clock instead: three marks
    separated by real `qtbot.wait(debounce_ms // 2)` sleeps, expecting one
    write. It passed alone and **failed inside the full unit run** (2 writes
    instead of 1) — because on a loaded machine `wait(75)` really can take
    longer than the 150ms window, so the timer fired mid-burst and the code
    was right while the test was wrong.

    Reading the countdown directly removes the race: a restart can only make
    the remaining time go *up*, and a slow machine only makes `before`
    smaller, which strengthens the assertion instead of breaking it.
    """
    debounce_ms = 2000  # far wider than any plausible scheduling delay
    coordinator = UiStateCoordinator(InMemoryStateStore(), debounce_ms=debounce_ms)
    contributor = _FakeContributor("dashboard")

    coordinator.mark_dirty(contributor)
    qtbot.wait(200)
    before = coordinator._timer.remainingTime()
    coordinator.mark_dirty(contributor)
    after = coordinator._timer.remainingTime()

    assert 0 < before < debounce_ms, "the first window should still be counting down"
    assert after > before, "the second mark must reset the countdown, not ride it out"


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
