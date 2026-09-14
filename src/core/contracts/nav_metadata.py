"""Navigation metadata a screen carries — the Published Language for the sidebar.

`EPIC-016` introduced this beside `ScreenRegistry`, when the registry was the
only thing that knew about navigation. `EPIC-025` makes it shared vocabulary:
every module that contributes a screen fills one in, the shell sorts them, and
`core/contracts` is where two sides of a boundary meet (HLD §2.4). Sorting still
happens exactly once, inside `ScreenRegistry.build_sidebar_navigation()`, and
only its *result* (plain `NavSection` / `NavItem` tuples) crosses into
`ISidebar` — `Sidebar`'s real contract has no `sequence` field and never gains
one (ADR D1,
`Tasks/epics/EPIC-016_screen_registry_pattern/DECISION_2026-08-30_screen_registry_pattern.md`).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NavLocation(str, Enum):
    """Where a screen's nav entry is placed on the sidebar."""

    TOP_SECTION = "TOP_SECTION"
    BOTTOM_ACTION = "BOTTOM_ACTION"


@dataclass(frozen=True, slots=True)
class NavMetadata:
    """One screen's navigation entry, before section/item ordering is resolved."""

    title: str
    icon: str
    section_key: str = "NAVIGATION"
    section_sequence: int = 100
    item_sequence: int = 100
    location: NavLocation = NavLocation.TOP_SECTION
    is_navigable: bool = True
