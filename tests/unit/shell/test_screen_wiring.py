"""Every screen the app has arrives as a contribution (SDD boot steps 6–7).

These tests pin the same routes, the same sidebar, the same lazy construction
the legacy `AbstractScreenModule` mechanism used to guarantee — but sourced
from the real bounded-context modules' own `contribute()`, the same call
`assemble_contributions()` makes, rather than from an adapter carrying a
strangler-period tenant.

`EPIC-025F` PR 5.2 retired the last four screens from that adapter
(`shell/legacy_screen_adapter.py`, deleted in this pull request) — this file
used to be about that adapter specifically (`contribute_legacy_screens`); now
it is about the same four screens' real modules instead, and a screen that
converts here does not move row, since there is no longer a legacy tree for
it to leave (`test_real_screen_modules.py`'s own precedent when `settings`
converted in `EPIC-025E` PR 4.4e).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.module import BacktestingModule
from Sagittarius_Elite_Warrior.src.modules.market_data.module import MarketDataModule
from Sagittarius_Elite_Warrior.src.modules.trading.module import TradingModule
from Sagittarius_Elite_Warrior.src.shell.contribution_registry import (
    ContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.shell.screen_wiring import build_screen_registry
from Sagittarius_Elite_Warrior.src.shell.welcome.welcome_screen import welcome_screen

_EXPECTED_ROUTES = (
    "dashboard",
    "trading",
    "data_management",
    "watchlist",
    "backtest",
)


def _real_modules(container: object) -> tuple[object, object, object]:
    """The three module instances that own these five screens (`BOT-019`
    added `watchlist` as `market_data`'s second screen), each with
    `_container` stashed the way `boot()` would (`TradingModule.__init__`
    and `BacktestingModule.__init__`'s own docstrings explain why this is
    safe to skip straight to). Ordered to match `_EXPECTED_ROUTES` — the
    order these were contributed in under the legacy mechanism this file
    used to test."""
    trading = TradingModule()
    trading._container = container
    market_data = MarketDataModule()
    backtesting = BacktestingModule()
    backtesting._container = container
    return trading, market_data, backtesting


def _contribute_screens(registry: ContributionRegistry, container: object) -> None:
    for module in _real_modules(container):
        module.contribute(registry)


def test_every_module_screen_is_contributed() -> None:
    registry = ContributionRegistry(dev_mode=False)
    _contribute_screens(registry, container=object())

    assert tuple(screen.route for screen in registry.screens()) == _EXPECTED_ROUTES


def test_each_screen_is_contributed_by_its_own_module_not_the_shell() -> None:
    """`contributor_id` is what a log line shows — each of these five is
    its module's own now, unlike the legacy mechanism's shared
    `LEGACY_CONTRIBUTOR_ID`."""
    registry = ContributionRegistry(dev_mode=False)
    _contribute_screens(registry, container=object())

    by_route = {screen.route: screen.contributor_id for screen in registry.screens()}
    assert by_route == {
        "dashboard": "trading",
        "trading": "trading",
        "data_management": "market_data",
        "watchlist": "market_data",
        "backtest": "backtesting",
    }


def test_the_default_route_survives_the_round_trip() -> None:
    """`welcome` (ADR D13), not any of the five module screens — none of
    them declares `is_default`. The round trip is the point: a default
    declared on a contribution has to still be the default after
    `ScreenRegistry` has it."""
    registry = ContributionRegistry(dev_mode=False)
    registry.contribute_screen(welcome_screen())
    _contribute_screens(registry, container=object())

    assert registry.default_route() == "welcome"
    assert build_screen_registry(registry).get_default_route() == "welcome"


def test_the_module_screens_alone_declare_no_default() -> None:
    registry = ContributionRegistry(dev_mode=False)
    _contribute_screens(registry, container=object())

    assert registry.default_route() is None


def test_no_view_is_built_while_contributing() -> None:
    """A screen's factory must stay unrun until first navigation — that
    laziness is what keeps boot from importing every screen's dependency
    tree. `container=object()` (not even a `Mock()`) is the proof: a
    factory that ran eagerly would crash on it immediately, since
    `dashboard_screen`/`backtest_screen`'s view factories call
    `container.resolve(...)`, which a plain `object()` cannot answer."""
    registry = ContributionRegistry(dev_mode=False)
    _contribute_screens(registry, container=object())

    for screen in registry.screens():
        assert callable(screen.view_factory)
        assert callable(screen.presenter_factory)


def test_the_sidebar_matches_the_legacy_layout() -> None:
    registry = ContributionRegistry(dev_mode=False)
    _contribute_screens(registry, container=object())

    sections, bottom = build_screen_registry(registry).build_sidebar_navigation()

    section_titles = [section.title for section in sections]
    assert section_titles == ["NAVIGATION", "QUANT ENGINE"]

    navigation_routes = [item.route for item in sections[0].items]
    assert navigation_routes == [
        "dashboard",
        "trading",
        "data_management",
        "watchlist",
    ]
    assert [item.route for item in sections[1].items] == ["backtest"]
    assert list(bottom) == []


def test_the_registry_holds_one_descriptor_per_route() -> None:
    registry = ContributionRegistry(dev_mode=False)
    _contribute_screens(registry, container=object())

    screen_registry = build_screen_registry(registry)
    assert (
        tuple(descriptor.route for descriptor in screen_registry.get_all())
        == _EXPECTED_ROUTES
    )
