"""`EPIC-043B` — the colour scheme the person chose last time is drawn from the first window on."""

from __future__ import annotations

import gc
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.presentation.ui import remembered_state_wiring
from Sagittarius_Elite_Warrior.src.presentation.ui.remembered_state_wiring import (
    register_remembered_state,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.colour_scheme_preference import (
    ColourSchemeChoice,
    ColourSchemePreference,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.adapters.in_memory_state_store import (
    InMemoryStateStore,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import StateScope
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer

_SCOPE = StateScope(key="colour_scheme")


class _Hints:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def setColorScheme(self, scheme: Qt.ColorScheme) -> None:  # noqa: N802
        self.calls.append(scheme.name)

    def unsetColorScheme(self) -> None:  # noqa: N802
        self.calls.append("unset")

    def colorScheme(self) -> Qt.ColorScheme:  # noqa: N802
        return Qt.ColorScheme.Unknown


@pytest.fixture
def hints(monkeypatch: pytest.MonkeyPatch) -> _Hints:
    recorder = _Hints()
    monkeypatch.setattr(
        remembered_state_wiring,
        "QGuiApplication",
        SimpleNamespace(styleHints=lambda: recorder),
    )
    return recorder


def _start(
    store: InMemoryStateStore,
) -> tuple[ColourSchemePreference, UiStateCoordinator]:
    container = StdLibContainer()
    coordinator = UiStateCoordinator(store)
    register_remembered_state(container, coordinator)
    return container.resolve(ColourSchemePreference), coordinator


def test_a_remembered_dark_is_asked_of_qt_at_start(hints: _Hints, qapp) -> None:
    store = InMemoryStateStore()
    store.write(_SCOPE, {"choice": "dark"})

    preference, _ = _start(store)

    assert preference.choice is ColourSchemeChoice.DARK
    assert hints.calls == ["Dark"]


def test_a_first_start_leaves_the_choice_to_the_platform(hints: _Hints, qapp) -> None:
    _start(InMemoryStateStore())

    assert hints.calls == ["unset"]


def test_a_choice_made_later_is_asked_of_qt_and_remembered(hints: _Hints, qapp) -> None:
    store = InMemoryStateStore()
    preference, coordinator = _start(store)
    hints.calls.clear()

    preference.set_choice(ColourSchemeChoice.LIGHT)
    coordinator.flush()

    assert hints.calls == ["Light"]
    assert store.read(_SCOPE) == {"choice": "light"}


def test_the_applier_outlives_the_wiring_that_built_it(hints: _Hints, qapp) -> None:
    """Nothing holds the applier but its subscription to the preference: a choice made after
    a garbage collection must still reach Qt."""
    preference, _ = _start(InMemoryStateStore())
    hints.calls.clear()
    gc.collect()

    preference.set_choice(ColourSchemeChoice.DARK)

    assert hints.calls == ["Dark"]
