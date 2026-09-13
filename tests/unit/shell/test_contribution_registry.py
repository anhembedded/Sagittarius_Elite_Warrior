"""The registry's five validation rules (SDD, "Registry validation").

Each test is one rule, named after what a reader would ask: *what happens if a
module gets this wrong?* The answers matter because they are the difference
between a typo caught at boot with the module's name in the message, and a panel
that silently never appears.
"""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts import (
    ContributionDescriptor,
    ContributionError,
    NavMetadata,
    Place,
    ScreenContribution,
    SizeHint,
)
from Sagittarius_Elite_Warrior.src.shell.contribution_registry import (
    ContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import DEV_MODE_GATE, Surface


def _never_called(_container: object) -> object:
    raise AssertionError("a factory must not run at contribute time")


def _descriptor(
    *,
    contributor_id: str = "market_data",
    surface_id: str = "trading",
    place: Place = Place.RAIL,
    order: int = 10,
    factory=_never_called,
    title: str | None = None,
) -> ContributionDescriptor:
    return ContributionDescriptor(
        contributor_id=contributor_id,
        surface_id=surface_id,
        place=place,
        order=order,
        size_hint=SizeHint.REGULAR,
        factory=factory,
        title=title,
    )


def _screen(route: str, *, is_default: bool = False) -> ScreenContribution:
    return ScreenContribution(
        contributor_id="market_data",
        route=route,
        view_factory=lambda: None,  # type: ignore[return-value]
        presenter_factory=lambda _view, _container: None,  # type: ignore[return-value]
        nav=NavMetadata(title=route.title(), icon="database"),
        is_default=is_default,
    )


@pytest.fixture
def registry() -> ContributionRegistry:
    return ContributionRegistry(dev_mode=True)


# --- rule 1: the surface and the place must exist -------------------------


def test_an_unknown_surface_is_a_typo_and_raises(
    registry: ContributionRegistry,
) -> None:
    with pytest.raises(ContributionError) as failure:
        registry.contribute(_descriptor(surface_id="tradng"))
    message = str(failure.value)
    assert "market_data" in message
    assert "tradng" in message
    assert "trading" in message  # the known surfaces, so the fix is visible


def test_a_place_the_surface_does_not_accept_raises(
    registry: ContributionRegistry,
) -> None:
    with pytest.raises(ContributionError) as failure:
        registry.contribute(_descriptor(surface_id="settings", place=Place.CONSOLE))
    assert "settings" in str(failure.value)
    assert "settings_section" in str(failure.value)


# --- rule 2: order sorts, it does not identify ----------------------------


def test_two_modules_may_both_pick_the_same_order(
    registry: ContributionRegistry,
) -> None:
    def first(_container: object) -> object: ...

    def second(_container: object) -> object: ...

    registry.contribute(_descriptor(contributor_id="strategy", order=10, factory=first))
    registry.contribute(
        _descriptor(contributor_id="market_data", order=10, factory=second)
    )

    rendered = registry.panels("trading", Place.RAIL)
    assert [descriptor.contributor_id for descriptor in rendered] == [
        "market_data",
        "strategy",
    ], "a tie breaks on contributor_id, deterministically"


def test_panels_come_back_in_order_then_contributor(
    registry: ContributionRegistry,
) -> None:
    def low(_container: object) -> object: ...

    def high(_container: object) -> object: ...

    registry.contribute(_descriptor(contributor_id="zzz", order=1, factory=low))
    registry.contribute(_descriptor(contributor_id="aaa", order=99, factory=high))
    assert [d.order for d in registry.panels("trading", Place.RAIL)] == [1, 99]


def test_the_same_factory_twice_in_one_place_raises(
    registry: ContributionRegistry,
) -> None:
    registry.contribute(_descriptor())
    with pytest.raises(ContributionError, match="twice"):
        registry.contribute(_descriptor())


def test_the_same_factory_on_two_surfaces_is_two_panels(
    registry: ContributionRegistry,
) -> None:
    """One widget class, many instances — that is what "one widget, many
    places" means (SDD, "Ownership of a contributed panel")."""
    registry.contribute(_descriptor(surface_id="trading"))
    registry.contribute(_descriptor(surface_id="dev_board"))
    assert len(registry.panels("trading", Place.RAIL)) == 1
    assert len(registry.panels("dev_board", Place.RAIL)) == 1


# --- rule 3: a gated-off surface drops, it does not raise -----------------


def test_a_gated_off_surface_drops_its_contributions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    registry = ContributionRegistry(dev_mode=False)
    with caplog.at_level(logging.INFO):
        registry.contribute(_descriptor(surface_id="dev_board", place=Place.DEV_PROBE))

    assert registry.panels("dev_board", Place.DEV_PROBE) == ()
    assert registry.dropped_count() == 1
    assert "dev_board" in caplog.text
    assert DEV_MODE_GATE in caplog.text


def test_a_gated_off_surface_still_validates_the_place() -> None:
    """Gated off is not "anything goes": a probe aimed at Settings is still a
    mistake, and the run that has developer mode off is exactly the run where
    nobody would notice it."""
    registry = ContributionRegistry(dev_mode=False)
    with pytest.raises(ContributionError):
        registry.contribute(_descriptor(surface_id="settings", place=Place.DEV_PROBE))


def test_with_developer_mode_on_the_gated_surface_accepts() -> None:
    registry = ContributionRegistry(dev_mode=True)
    registry.contribute(_descriptor(surface_id="dev_board", place=Place.DEV_PROBE))
    assert len(registry.panels("dev_board", Place.DEV_PROBE)) == 1
    assert registry.dropped_count() == 0


# --- rule 4: no factory runs during contribute() --------------------------


def test_no_factory_is_called_while_contributing(
    registry: ContributionRegistry,
) -> None:
    registry.contribute(_descriptor(factory=_never_called))
    registry.contribute_screen(_screen("data_management"))
    # `_never_called` raises if invoked; reaching here is the assertion.
    assert registry.panels("trading", Place.RAIL)[0].factory is _never_called


# --- screens --------------------------------------------------------------


def test_a_duplicate_route_raises(registry: ContributionRegistry) -> None:
    registry.contribute_screen(_screen("trading"))
    with pytest.raises(ContributionError, match="contributed twice"):
        registry.contribute_screen(_screen("trading"))


def test_two_default_screens_raise(registry: ContributionRegistry) -> None:
    registry.contribute_screen(_screen("dashboard", is_default=True))
    with pytest.raises(ContributionError, match="two default screens"):
        registry.contribute_screen(_screen("trading", is_default=True))


def test_the_default_route_is_the_screen_that_claimed_it(
    registry: ContributionRegistry,
) -> None:
    registry.contribute_screen(_screen("trading"))
    registry.contribute_screen(_screen("dashboard", is_default=True))
    assert registry.default_route() == "dashboard"


def test_screens_keep_the_order_they_were_contributed_in(
    registry: ContributionRegistry,
) -> None:
    for route in ("dashboard", "trading", "settings"):
        registry.contribute_screen(_screen(route))
    assert [screen.route for screen in registry.screens()] == [
        "dashboard",
        "trading",
        "settings",
    ]


# --- the surface table itself --------------------------------------------


def test_a_surface_with_an_unknown_gate_fails_loudly() -> None:
    surface = Surface(
        "odd", owner="shell", accepts=frozenset({Place.RAIL}), gated_by="nope"
    )
    with pytest.raises(ValueError, match="unknown gate"):
        surface.is_open_in(dev_mode=True)


def test_an_ungated_surface_is_always_open() -> None:
    surface = Surface("welcome", owner="shell", accepts=frozenset({Place.WORKSPACE}))
    assert surface.is_open_in(dev_mode=False)
