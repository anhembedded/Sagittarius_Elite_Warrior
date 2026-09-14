"""A whole navigable screen, contributed (SDD, "the contribution descriptor").

The one exception to `ContributionDescriptor`'s single shape, and it earns the
exception: navigation metadata already exists as `NavMetadata` and is consumed
by the sidebar unchanged, so a screen carries that instead of a `place` and a
`size_hint`. Its factory pair is the pair `ScreenRegistry` already expects — a
view factory and a presenter factory — which is what lets the shell wrap the
strangler period's five legacy screens as contributions
(`shell/legacy_screen_adapter.py`) without touching them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata

if TYPE_CHECKING:
    from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
    from sagittarius_engine.interfaces.i_container import IContainer


@dataclass(frozen=True, slots=True)
class ScreenContribution:
    """One route, its sidebar entry, and how to build it when first shown."""

    contributor_id: str
    route: str
    view_factory: Callable[[], BaseView]
    presenter_factory: Callable[[BaseView, IContainer], BasePresenter]
    #: `None` means "reachable, but not listed in the sidebar".
    nav: NavMetadata | None = None
    #: Exactly one screen in a run may be the default; the shell checks.
    is_default: bool = False
