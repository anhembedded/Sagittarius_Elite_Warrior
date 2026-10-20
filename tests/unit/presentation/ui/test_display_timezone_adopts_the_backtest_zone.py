"""`BOT-205` — an owner's Backtest time zone survives the move to the shared setting.

The zone used to be a field of the Backtest's own remembered slice. A silent reset to UTC is what
`BUG-234` was about, so the first start after the move adopts that zone, once: only while the
shared setting has no value of its own.

Retire when: no installed copy can still hold a Backtest slice with a `timezone` key (the
Backtest rewrites its slice without it on its first save, so one session after the move)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.remembered_state_wiring import (
    register_remembered_state,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.adapters.in_memory_state_store import (
    InMemoryStateStore,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import StateScope
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer

_BACKTEST = StateScope(key="backtest")
_SHARED = StateScope(key="display_timezone")


def _start(
    store: InMemoryStateStore,
) -> tuple[DisplayTimezonePreference, UiStateCoordinator]:
    container = StdLibContainer()
    coordinator = UiStateCoordinator(store)
    register_remembered_state(container, coordinator)
    return container.resolve(DisplayTimezonePreference), coordinator


def test_the_first_start_adopts_the_zone_the_backtest_remembered(qapp) -> None:
    store = InMemoryStateStore()
    store.write(_BACKTEST, {"timezone": "Asia/Ho_Chi_Minh", "symbol": "BTCUSDT"})

    preference, coordinator = _start(store)
    coordinator.flush()

    assert preference.zone == "Asia/Ho_Chi_Minh"
    assert store.read(_SHARED) == {"zone": "Asia/Ho_Chi_Minh"}


def test_the_shared_setting_wins_once_it_has_a_value(qapp) -> None:
    store = InMemoryStateStore()
    store.write(_BACKTEST, {"timezone": "Asia/Ho_Chi_Minh"})
    store.write(_SHARED, {"zone": "UTC"})

    preference, _ = _start(store)

    assert preference.zone == "UTC"


def test_an_old_zone_no_picker_offers_is_not_adopted(qapp) -> None:
    store = InMemoryStateStore()
    store.write(_BACKTEST, {"timezone": "Atlantis/Lost"})

    preference, _ = _start(store)

    assert preference.zone == "UTC"
