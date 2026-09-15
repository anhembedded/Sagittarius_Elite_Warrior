"""The Welcome screen as a contribution — the shell's own (ADR D13).

Every other navigable screen is either a legacy `AbstractScreenModule` the
shell carries or (later) a module's. This one belongs to the shell itself,
because it is about the *application* rather than about any bounded context
(HLD §4.6's own rule for what a shell surface is), and it arrives through the
same `ScreenContribution` everything else does — so `ScreenRegistry`,
`PresenterManager` and the sidebar never learn that a third kind of screen
exists.

It is the **default route** (ADR D13): the app opens here rather than on a
developer testbed that happened to be first in the sidebar.
`ContributionRegistry` refuses a second default, so the day another screen
claims it, boot fails and says which two.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.contribution_descriptor import (
    SHELL_CONTRIBUTOR_ID,
)
from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from sagittarius_engine.interfaces.i_container import IContainer

if TYPE_CHECKING:
    # Annotations only: importing `pyside_mvc` for real pulls Qt in, which is
    # exactly what the two lazy factories below exist to avoid.
    from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView

WELCOME_ROUTE = "welcome"

#: First in the sidebar's own section, above the trading screens: a user
#: returning to Welcome is going back to the start, not sideways.
_NAV = NavMetadata(
    title="Welcome",
    # `zap`, not `home`: the icon set is Lucide's, vendored under
    # `assets/icons/`, and it has no `home.svg` — `IconLoader` answers a
    # missing name with a blank glyph *and a WARNING*, which the gate's log
    # scan fails on. Measured, not guessed: the first version of this file
    # asked for `home` and the gate said so.
    icon="zap",
    section_key="NAVIGATION",
    section_sequence=10,
    item_sequence=5,
)


def _build_welcome_view() -> BaseView:
    """Builds the view, importing it only now.

    The same shape `presentation/ui/screens/*/module.py` uses for its own
    `create_view()`, and for the same reason: this file is imported by
    `shell/contribution_assembly.py`, which the **headless** entry point
    imports too. A `WelcomeView` named at module level here would make
    `python -m ...main sync` import Qt to answer a question it never asks.
    """
    from Sagittarius_Elite_Warrior.src.shell.welcome.welcome_view import WelcomeView

    return WelcomeView()


def _build_welcome_presenter(view: BaseView, container: IContainer) -> BasePresenter:
    """Builds the Presenter, checking the view it was handed.

    `ScreenContribution.presenter_factory` is typed over `BaseView` — it has to
    be, since the registry builds every screen the same way — while
    `WelcomePresenter` needs *this* view's two signals. The check is real, not
    a cast to satisfy `mypy`: a wiring mistake that paired this presenter with
    another screen's view would otherwise fail later, inside a slot, with an
    `AttributeError` naming nothing useful. `shell/` is inside the type gate,
    which is how this was caught at all.
    """
    from Sagittarius_Elite_Warrior.src.shell.welcome.welcome_presenter import (
        WelcomePresenter,
    )
    from Sagittarius_Elite_Warrior.src.shell.welcome.welcome_view import WelcomeView

    if not isinstance(view, WelcomeView):
        raise TypeError(
            f"the Welcome screen's presenter was handed a {type(view).__name__}, "
            "not a WelcomeView"
        )
    return WelcomePresenter(view, container)


def welcome_screen() -> ScreenContribution:
    """The shell's Welcome screen, described the way a module would describe
    one."""
    return ScreenContribution(
        contributor_id=SHELL_CONTRIBUTOR_ID,
        route=WELCOME_ROUTE,
        view_factory=_build_welcome_view,
        presenter_factory=_build_welcome_presenter,
        nav=_NAV,
        is_default=True,
    )
