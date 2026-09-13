"""The strangler period's five screens, seen as contributions (SDD, boot step 6).

Phase 0 introduces the mechanism; it does not migrate the screens. Those five
`AbstractScreenModule`s stay exactly as they are — same routes, same sidebar
entries, same lazy factories — and this adapter is how the shell stops knowing
them by name: it turns each one into a `ScreenContribution`, which is the same
thing every future module will hand over. The hard-coded tuple in
`app_bootstrapper.py` becomes a list the shell walks; when Phase 1 replaces
`TradingScreenModule` with `modules/trading`, the shell's code does not change,
only the list does.

Deleted in Phase 4, with the last `AbstractScreenModule`.

Why it converts rather than wrapping the registry: `ScreenRegistry` already does
section reconciliation and sidebar ordering correctly, and `PresenterManager`
already caches per route. Re-implementing either in the shell for the sake of
symmetry would be a rewrite disguised as an adapter.
"""

from __future__ import annotations

from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.registry import AbstractScreenModule
from Sagittarius_Elite_Warrior.src.presentation.ui.registry.models import (
    ScreenDescriptor,
)
from sagittarius_engine.interfaces.i_container import IContainer

#: `contributor_id` for a screen that has no module yet. Not `"shell"`: the
#: shell did not write these screens, it is only carrying them until their
#: bounded context claims them, and the id is what says so in a log line.
LEGACY_CONTRIBUTOR_ID = "legacy"


def as_screen_contribution(
    module: AbstractScreenModule, container: IContainer
) -> ScreenContribution:
    """One legacy screen module, described the way a module would describe it."""
    descriptor = module.build_descriptor(container)
    return ScreenContribution(
        contributor_id=LEGACY_CONTRIBUTOR_ID,
        route=descriptor.route,
        view_factory=descriptor.view_factory,
        presenter_factory=descriptor.presenter_class,
        nav=descriptor.nav,
        is_default=descriptor.is_default,
    )


def legacy_screen_contributions(
    modules: Iterable[AbstractScreenModule], container: IContainer
) -> tuple[ScreenContribution, ...]:
    return tuple(as_screen_contribution(module, container) for module in modules)


def as_screen_descriptor(contribution: ScreenContribution) -> ScreenDescriptor:
    """The reverse direction: a contribution, ready for `ScreenRegistry`.

    Every screen — legacy or contributed by a real module — goes through this
    one function, so the registry never learns that two kinds exist.
    """
    return ScreenDescriptor(
        route=contribution.route,
        presenter_class=contribution.presenter_factory,
        view_factory=contribution.view_factory,
        nav=contribution.nav,
        is_default=contribution.is_default,
    )
