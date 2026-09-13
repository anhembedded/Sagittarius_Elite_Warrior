"""From contributions to a populated `ScreenRegistry` (SDD boot steps 6–7).

One function, so there is exactly one path from "something contributed a screen"
to "the sidebar has an entry for it" — whether that something is a bounded
context or the adapter carrying a legacy screen. `MainWindow` and
`PresenterManager` are untouched: they still receive an `IScreenRegistry` and
still build each view lazily on first navigation.

The order screens are registered in does not matter (`ScreenRegistry` sorts by
each screen's declared section and item sequence), but the order they are
*contributed* in does, so this function preserves it: a future module's rail
panels appear in `MODULES` order, and a reader can predict the sidebar from two
lists in `src/shell/`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_registry import (
    IContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.registry import (
    IScreenRegistry,
    ScreenRegistry,
)
from Sagittarius_Elite_Warrior.src.shell.contribution_registry import (
    ContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.shell.legacy_screen_adapter import (
    as_screen_descriptor,
    legacy_screen_contributions,
)
from Sagittarius_Elite_Warrior.src.shell.legacy_screens import LEGACY_SCREEN_MODULES
from sagittarius_engine.interfaces.i_container import IContainer


def contribute_legacy_screens(
    registry: IContributionRegistry, container: IContainer
) -> None:
    """Hand every screen the strangler period still carries to the registry."""
    for contribution in legacy_screen_contributions(
        (module_cls() for module_cls in LEGACY_SCREEN_MODULES), container
    ):
        registry.contribute_screen(contribution)


def build_screen_registry(contributions: ContributionRegistry) -> IScreenRegistry:
    """The navigable screens of this run, as `MainWindow` needs them."""
    screen_registry = ScreenRegistry()
    for contribution in contributions.screens():
        screen_registry.register(as_screen_descriptor(contribution))
    return screen_registry
