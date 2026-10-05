"""A whole navigable screen, contributed (SDD, "the contribution descriptor").

The one exception to `ContributionDescriptor`'s single shape, and it earns the
exception: navigation metadata already exists as `NavMetadata` and is consumed
by the mode bar unchanged, so a screen carries that instead of a `place` and a
`size_hint`. Its factory pair is the pair `ScreenRegistry` already expects — a
view factory and a presenter factory — the same shape every screen in this
codebase describes itself with (`EPIC-025F` PR 5.2).
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
    """One route, its mode-bar entry, and how to build it."""

    contributor_id: str
    route: str
    view_factory: Callable[[], BaseView]
    presenter_factory: Callable[[BaseView, IContainer], BasePresenter]
    #: `None` means "registered, but not a mode".
    nav: NavMetadata | None = None
    #: Exactly one screen in a run may be the default; the shell checks.
    is_default: bool = False
    #: A run-time condition the mode exists under (`"dev.mode"`), as a
    #: gated `Surface` has: off, the screen is dropped with a log line, and
    #: so are the commands of its mode (`EPIC-033P`).
    gated_by: str | None = None
