"""`EPIC-043D` — whether a price flashes is registered at start, off on a first start, and
remembered: the Options page and the Market mode both find the one preference in the container."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.remembered_state_wiring import (
    register_remembered_state,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.tick_flash_preference import (
    TickFlashPreference,
    find_tick_flash_preference,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.adapters.in_memory_state_store import (
    InMemoryStateStore,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import StateScope
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer

_SCOPE = StateScope(key="tick_flash")


def _start(store: InMemoryStateStore):
    container = StdLibContainer()
    coordinator = UiStateCoordinator(store)
    register_remembered_state(container, coordinator)
    return container, coordinator


def test_a_first_start_has_the_flash_off(qapp) -> None:
    container, _ = _start(InMemoryStateStore())

    assert container.resolve(TickFlashPreference).enabled is False


def test_a_remembered_on_is_on_from_the_first_window(qapp) -> None:
    store = InMemoryStateStore()
    store.write(_SCOPE, {"enabled": True})

    container, _ = _start(store)

    assert find_tick_flash_preference(container) is container.resolve(
        TickFlashPreference
    )
    assert container.resolve(TickFlashPreference).enabled is True


def test_a_change_is_remembered(qapp) -> None:
    store = InMemoryStateStore()
    container, coordinator = _start(store)

    container.resolve(TickFlashPreference).set_enabled(True)
    coordinator.flush()

    assert store.read(_SCOPE) == {"enabled": True}


def test_a_container_that_registered_none_gives_none(qapp) -> None:
    assert find_tick_flash_preference(StdLibContainer()) is None
