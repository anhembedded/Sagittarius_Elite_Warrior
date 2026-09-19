"""From contributions to a populated `ScreenRegistry` (SDD boot steps 6–7).

One function, so there is exactly one path from "something contributed a
screen" to "the sidebar has an entry for it" — whether that something is a
bounded context or the shell's own Welcome/Settings. `MainWindow` and
`PresenterManager` are untouched: they still receive an `IScreenRegistry` and
still build each view lazily on first navigation.

`EPIC-025F` PR 5.2 retired the last of the strangler-period screens this file
used to carry through an adapter (`shell/legacy_screen_adapter.py`, deleted in
the same pull request): every navigable screen now describes itself as a
`ScreenContribution` at its own address, the way `settings_screen()` and
`welcome_screen()` already did — `dashboard`/`trading` (`modules/trading`),
`data_management` (`modules/market_data`), `backtest` (`modules/backtesting`).
This file's one remaining job is the one direction `ContributionRegistry`
does not do on its own: turning a `ScreenContribution` into the
`ScreenDescriptor` `ScreenRegistry` stores.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from Sagittarius_Elite_Warrior.src.shell.contribution_registry import (
    ContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import (
    IScreenRegistry,
    ScreenRegistry,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry.models import (
    ScreenDescriptor,
)


def as_screen_descriptor(contribution: ScreenContribution) -> ScreenDescriptor:
    """Every screen — shell-owned or module-contributed — goes through this
    one function, so the registry never learns that a screen came from
    anywhere in particular."""
    return ScreenDescriptor(
        route=contribution.route,
        presenter_class=contribution.presenter_factory,
        view_factory=contribution.view_factory,
        nav=contribution.nav,
        is_default=contribution.is_default,
    )


def build_screen_registry(contributions: ContributionRegistry) -> IScreenRegistry:
    """The navigable screens of this run, as `MainWindow` needs them."""
    screen_registry = ScreenRegistry()
    for contribution in contributions.screens():
        screen_registry.register(as_screen_descriptor(contribution))
    return screen_registry
