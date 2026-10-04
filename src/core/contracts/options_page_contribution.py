"""A page of Tools → Options, contributed (`EPIC-033E`).

The Settings screen's `SETTINGS_SECTION` place rendered a module's form as a
group box with its own Save button. Options pages are not widgets placed on a
surface: the dialog drives them (apply, revert, dirty), so a contribution
names a page, not a widget, the way `ScreenContribution` names a screen.

`factory` builds the page when the shell assembles the dialog's pages; it is
a `Deferred` in the modules, so `contribute()` imports no widget module
(`test_module_contribution_laziness.py`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.core.contracts.i_options_section import (
        IOptionsSection,
    )
    from sagittarius_engine.interfaces.i_container import IContainer


@dataclass(frozen=True, slots=True)
class OptionsPageContribution:
    """One module's page of Tools → Options."""

    contributor_id: str
    #: The page's place in the section list: lower first, ties by contributor.
    order: int
    factory: Callable[[IContainer], IOptionsSection]
