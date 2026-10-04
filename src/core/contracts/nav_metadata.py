"""Navigation metadata a screen carries — the Published Language for the mode bar.

`EPIC-016` introduced this beside `ScreenRegistry`, when the registry was the
only thing that knew about navigation. `EPIC-025` makes it shared vocabulary:
every module that contributes a screen fills one in, the shell sorts them, and
`core/contracts` is where two sides of a boundary meet (HLD §2.4). Sorting
happens exactly once, inside `ScreenRegistry.modes()`, and only its *result*,
the ordered screens, reaches the workbench window's mode bar (`EPIC-033C`,
which replaced the sidebar; ADR D1,
`Tasks/epics/EPIC-016_screen_registry_pattern/DECISION_2026-08-30_screen_registry_pattern.md`).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NavLocation(str, Enum):
    """Where a screen's mode sits on the mode bar: bottom actions come last."""

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
