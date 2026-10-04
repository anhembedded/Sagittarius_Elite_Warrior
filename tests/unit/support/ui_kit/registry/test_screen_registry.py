"""`EPIC-016` / `EPIC-025F` — `ScreenRegistry` behaviour, independent of any real screen."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import (
    NavLocation,
    NavMetadata,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import (
    ScreenDescriptor,
    ScreenRegistry,
    SectionDescriptor,
)


def _make_descriptor(
    route: str,
    *,
    title: str = "",
    icon: str = "",
    section_key: str = "NAVIGATION",
    section_sequence: int = 100,
    item_sequence: int = 100,
    is_default: bool = False,
    location: NavLocation = NavLocation.TOP_SECTION,
    navigable: bool = True,
    presenter_class=None,
    view_factory=None,
) -> ScreenDescriptor:
    nav = NavMetadata(
        title=title or route,
        icon=icon,
        section_key=section_key,
        section_sequence=section_sequence,
        item_sequence=item_sequence,
        location=location,
        is_navigable=navigable,
    )
    return ScreenDescriptor(
        route=route,
        presenter_class=presenter_class or (lambda v, c: Mock()),
        view_factory=view_factory or (lambda: Mock()),
        nav=nav,
        is_default=is_default,
    )


@pytest.fixture
def registry() -> ScreenRegistry:
    return ScreenRegistry()


def test_register_then_get_returns_its_descriptor(registry) -> None:
    descriptor = _make_descriptor("dashboard", title="Dev Board")
    registry.register(descriptor)
    retrieved = registry.get("dashboard")
    assert retrieved.route == "dashboard"
    assert retrieved.nav is not None
    assert retrieved.nav.title == "Dev Board"


def test_get_unknown_route_raises_key_error(registry) -> None:
    with pytest.raises(KeyError):
        registry.get("nope")


def test_get_default_route_raises_when_nothing_declared_default(registry) -> None:
    with pytest.raises(RuntimeError):
        registry.get_default_route()


def test_duplicate_route_raises_value_error(registry) -> None:
    registry.register(_make_descriptor("dashboard"))
    with pytest.raises(ValueError, match="dashboard"):
        registry.register(_make_descriptor("dashboard"))


def test_two_default_screens_raises_value_error(registry) -> None:
    registry.register(_make_descriptor("a", is_default=True))
    with pytest.raises(ValueError, match="is_default"):
        registry.register(_make_descriptor("b", is_default=True))


def _routes(registry) -> list[str]:
    return [descriptor.route for descriptor in registry.modes()]


def test_modes_sort_by_section_then_item(registry) -> None:
    registry.register(
        _make_descriptor(
            "backtest", title="Backtest", section_key="QUANT", section_sequence=20
        )
    )
    registry.register(
        _make_descriptor(
            "dashboard",
            title="Dev Board",
            section_key="NAV",
            section_sequence=10,
            item_sequence=10,
        )
    )
    registry.register(
        _make_descriptor(
            "data_management",
            title="Database",
            section_key="NAV",
            section_sequence=10,
            item_sequence=20,
        )
    )

    assert _routes(registry) == ["dashboard", "data_management", "backtest"]


def test_bottom_action_screens_come_last(registry) -> None:
    registry.register(
        _make_descriptor(
            "settings", title="Settings", location=NavLocation.BOTTOM_ACTION
        )
    )
    registry.register(_make_descriptor("dashboard", section_sequence=900))

    assert _routes(registry) == ["dashboard", "settings"]


def test_a_screen_that_is_not_navigable_is_not_a_mode(registry) -> None:
    registry.register(_make_descriptor("dashboard"))
    registry.register(
        ScreenDescriptor(
            route="hidden",
            presenter_class=Mock(),
            view_factory=Mock(),
            nav=NavMetadata(title="Hidden", icon="x", is_navigable=False),
        )
    )
    registry.register(
        ScreenDescriptor(route="no_nav", presenter_class=Mock(), view_factory=Mock())
    )

    assert _routes(registry) == ["dashboard"]


def test_item_sequence_tie_break_is_deterministic_by_route(registry) -> None:
    registry.register(
        _make_descriptor("b_route", title="B", section_key="NAV", item_sequence=10)
    )
    registry.register(
        _make_descriptor("a_route", title="A", section_key="NAV", item_sequence=10)
    )

    assert _routes(registry) == ["a_route", "b_route"]


def test_conflicting_section_sequence_across_screens_raises(registry) -> None:
    registry.register(_make_descriptor("a", section_key="NAV", section_sequence=10))
    with pytest.raises(ValueError, match="section_sequence conflict"):
        registry.register(
            _make_descriptor("b", section_key="NAV", section_sequence=999)
        )


def test_register_section_locks_the_sequence_explicitly(registry) -> None:
    registry.register_section(SectionDescriptor(key="LATE", title="Late", sequence=50))
    registry.register(
        _make_descriptor("early", section_key="EARLY", section_sequence=10)
    )
    registry.register(_make_descriptor("late", section_key="LATE", section_sequence=50))
    registry.register_section(SectionDescriptor(key="LATE", title="Late", sequence=1))

    assert _routes(registry) == ["late", "early"]


def test_register_accepts_a_descriptor_without_nav(registry) -> None:
    descriptor = ScreenDescriptor(
        route="fake",
        presenter_class=lambda v, c: Mock(),
        view_factory=lambda: Mock(),
    )
    registry.register(descriptor)
    assert registry.get("fake") is descriptor
