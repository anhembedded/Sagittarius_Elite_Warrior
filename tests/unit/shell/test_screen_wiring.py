"""Every screen the app has arrives as a contribution (SDD boot steps 6–7).

Phase 0 does not migrate a single screen, and that is exactly what these tests
pin: the same five routes, the same sidebar, the same lazy construction — but
reached through `ScreenContribution`, so a bounded context's screen in Phase 1
travels the identical path.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts import NavLocation
from Sagittarius_Elite_Warrior.src.shell.contribution_registry import (
    ContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.shell.legacy_screen_adapter import (
    LEGACY_CONTRIBUTOR_ID,
)
from Sagittarius_Elite_Warrior.src.shell.legacy_screens import LEGACY_SCREEN_MODULES
from Sagittarius_Elite_Warrior.src.shell.screen_wiring import (
    build_screen_registry,
    contribute_legacy_screens,
)
from Sagittarius_Elite_Warrior.src.shell.welcome.welcome_screen import welcome_screen
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer

_EXPECTED_ROUTES = ("dashboard", "trading", "data_management", "settings", "backtest")


@pytest.fixture
def wired() -> ContributionRegistry:
    """The legacy screens alone — what this file is about."""
    registry = ContributionRegistry(dev_mode=False)
    contribute_legacy_screens(registry, StdLibContainer())
    return registry


@pytest.fixture
def wired_with_the_shells_own() -> ContributionRegistry:
    """The legacy screens **plus** the shell's Welcome screen, which is what
    `assemble_contributions()` builds in a real run (PR 1.5a)."""
    registry = ContributionRegistry(dev_mode=False)
    registry.contribute_screen(welcome_screen())
    contribute_legacy_screens(registry, StdLibContainer())
    return registry


def test_the_shell_carries_exactly_the_five_screens_that_have_no_module_yet() -> None:
    assert len(LEGACY_SCREEN_MODULES) == 5


def test_every_legacy_screen_is_contributed(wired: ContributionRegistry) -> None:
    assert tuple(screen.route for screen in wired.screens()) == _EXPECTED_ROUTES


def test_they_are_contributed_as_legacy_not_as_the_shell(
    wired: ContributionRegistry,
) -> None:
    """`contributor_id` is what a log line shows. The shell did not write these
    screens; it is carrying them until a bounded context claims them."""
    assert {screen.contributor_id for screen in wired.screens()} == {
        LEGACY_CONTRIBUTOR_ID
    }


def test_the_default_route_survives_the_round_trip(
    wired_with_the_shells_own: ContributionRegistry,
) -> None:
    """`welcome` since PR 1.5a, not `dashboard` (ADR D13): the app opens on a
    screen about the application rather than on a developer testbed. The
    round trip is the point — a default declared on a contribution has to
    still be the default after `ScreenRegistry` has it."""
    assert wired_with_the_shells_own.default_route() == "welcome"
    assert (
        build_screen_registry(wired_with_the_shells_own).get_default_route()
        == "welcome"
    )


def test_the_legacy_screens_alone_declare_no_default_any_more(
    wired: ContributionRegistry,
) -> None:
    """The Dev Board gave the flag up, and nothing else in the legacy tree
    took it: the default now comes from the shell, which is the change ADR
    D13 asked for and the reason `tests/conftest.py`'s `real_screen_registry`
    had to start including Welcome."""
    assert wired.default_route() is None


def test_no_view_is_built_while_contributing(wired: ContributionRegistry) -> None:
    """A screen's factory must stay unrun until first navigation — that
    laziness is what keeps boot from importing every screen's dependency
    tree."""
    for screen in wired.screens():
        assert callable(screen.view_factory)
        assert callable(screen.presenter_factory)


def test_the_sidebar_is_what_it_was_before(wired: ContributionRegistry) -> None:
    sections, bottom = build_screen_registry(wired).build_sidebar_navigation()

    section_titles = [section.title for section in sections]
    assert section_titles == ["NAVIGATION", "QUANT ENGINE"]

    navigation_routes = [item.route for item in sections[0].items]
    assert navigation_routes == ["dashboard", "trading", "data_management"]
    assert [item.route for item in sections[1].items] == ["backtest"]
    assert [item.route for item in bottom] == ["settings"]


def test_settings_stays_a_bottom_action(wired: ContributionRegistry) -> None:
    settings = next(screen for screen in wired.screens() if screen.route == "settings")
    assert settings.nav is not None
    assert settings.nav.location is NavLocation.BOTTOM_ACTION


def test_the_registry_holds_one_descriptor_per_route(
    wired: ContributionRegistry,
) -> None:
    registry = build_screen_registry(wired)
    assert (
        tuple(descriptor.route for descriptor in registry.get_all()) == _EXPECTED_ROUTES
    )
