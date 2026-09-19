"""Why a navigation happened — the distinction `BUG-104`/`BUG-107` needed and
never had. `EPIC-010C` restoring `last_route` and a real sidebar click both
called `MainWindow.switch_screen()` the same way; a screen whose own design
is "being open means live" (`TradingPresenter`, `EPIC-021I`) could not tell
the two apart, so a restored route silently re-triggered live side effects.
`core/contracts` is where the shell and `NavigationService` (`EPIC-025F`)
agree on this vocabulary (HLD §2.4), mirroring `nav_metadata.py`'s
`NavLocation` in the same directory.
"""

from __future__ import annotations

from enum import Enum


class NavigationSource(str, Enum):
    """Why `NavigationService.navigate()` was called."""

    #: A real user action — a sidebar click, a menu action, a button.
    USER_INTENT = "USER_INTENT"
    #: The shell replaying a previously remembered route (state restore),
    #: with no click behind it.
    RESTORE = "RESTORE"
