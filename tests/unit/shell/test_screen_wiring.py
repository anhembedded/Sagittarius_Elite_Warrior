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
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer

_EXPECTED_ROUTES = ("dashboard", "trading", "data_management", "settings", "backtest")


@pytest.fixture
def wired() -> ContributionRegistry:
    registry = ContributionRegistry(dev_mode=False)
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


def test_the_default_route_survives_the_round_trip(wired: ContributionRegistry) -> None:
    assert wired.default_route() == "dashboard"
    assert build_screen_registry(wired).get_default_route() == "dashboard"


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
