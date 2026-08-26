"""`EPIC-010D` — finding the coordinator from a presenter, safely.

@details `PresenterManager` builds every screen as
`presenter_class(view, container)`, with no seam for extra constructor
arguments, so a presenter that wants the `UiStateCoordinator` has to ask the
container for it. But persistence is optional: presenters are constructed in
tests against containers that know nothing about it, and were constructed in
production that way too until `app_bootstrapper` was wired.

This lives in one place rather than being repeated per presenter, and it is
deliberately conservative about what it expects a container to be. The first
version inlined `UiStateCoordinator in container.registrations()` in each
presenter, which broke 35 existing tests: `IContainer.registrations()` is
declared to return a `Mapping`, but a plain `unittest.mock.Mock` double
returns another `Mock`, and `in` on a `Mock` raises `TypeError` (only
`MagicMock` implements `__contains__`). A container that cannot say what it
holds, in the shape its own interface promises, is treated as holding
nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.presentation.ui.state.ui_state_coordinator import (
    UiStateCoordinator,
)

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer


def find_state_coordinator(container: IContainer) -> UiStateCoordinator | None:
    """The registered `UiStateCoordinator`, or `None` when there isn't one.

    @details Never raises, and never returns a value the caller would have to
    re-check: a screen with no coordinator simply keeps its own defaults.
    """
    registrations = container.registrations()
    if not isinstance(registrations, Mapping):
        return None
    if UiStateCoordinator not in registrations:
        return None
    resolved = container.resolve(UiStateCoordinator)
    return resolved if isinstance(resolved, UiStateCoordinator) else None
