"""`EPIC-016` — navigation metadata a `ScreenDescriptor` carries.

@details Registry-internal only (ADR D1,
`Tasks/epics/EPIC-016_screen_registry_pattern/DECISION_2026-08-30_screen_registry_pattern.md`):
`Sidebar`'s real contract (`SidebarSection`/`ITab`, aliased as
`NavSection`/`NavItem`) has no `sequence` field and never gains one — sorting
happens once, inside `ScreenRegistry.build_sidebar_navigation()`, and only
its *result* (plain `NavSection`/`NavItem` tuples) crosses into `ISidebar`.
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
