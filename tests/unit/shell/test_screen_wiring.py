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
from Sagittarius_Elite_Warrior.src.modules.bots.module import BotsModule
from Sagittarius_Elite_Warrior.src.modules.market_data.module import MarketDataModule
from Sagittarius_Elite_Warrior.src.modules.trading.module import TradingModule
from Sagittarius_Elite_Warrior.src.shell.contribution_registry import (
    ContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.shell.screen_wiring import build_screen_registry

_EXPECTED_ROUTES = (
    # `EPIC-033H` — the Market mode, `trading`'s first contribution.
    "market",
    # `EPIC-033I` — one Trade mode for every venue, replacing the two desks
    # of `EPIC-028K`/`028L` (which had replaced the single Trading screen).
    "trade",
    "data_management",
    "backtest",
    # `EPIC-029F` — bots contribute last, `MODULES` order.
    "bots",
)


def _real_modules(container: object) -> tuple[object, object, object, object]:
    """The four module instances that own these six screens (`EPIC-029F`
    added the Bots tab; `EPIC-033H` replaced `market_data`'s Watchlist screen
    with `trading`'s Market mode; `EPIC-033P` deleted the Dev Board), each with
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
    return trading, market_data, backtesting, BotsModule()


def _contribute_screens(registry: ContributionRegistry, container: object) -> None:
    for module in _real_modules(container):
        module.contribute(registry)


def test_every_module_screen_is_contributed() -> None:
    registry = ContributionRegistry(dev_mode=False)
    _contribute_screens(registry, container=object())

    assert tuple(screen.route for screen in registry.screens()) == _EXPECTED_ROUTES


def test_each_screen_is_contributed_by_its_own_module_not_the_shell() -> None:
    """`contributor_id` is what a log line shows — each of these six is
    its module's own now, unlike the legacy mechanism's shared
    `LEGACY_CONTRIBUTOR_ID`."""
    registry = ContributionRegistry(dev_mode=False)
    _contribute_screens(registry, container=object())

    by_route = {screen.route: screen.contributor_id for screen in registry.screens()}
    assert by_route == {
        "market": "trading",
        "trade": "trading",
        "data_management": "market_data",
        "backtest": "backtesting",
        "bots": "bots",
    }


def test_the_default_route_survives_the_round_trip() -> None:
    """The Trade mode (`EPIC-033I`, the Futures desk before it,
    `EPIC-033C`): the first run opens there, as the deleted Welcome
    screen's Start did. The round trip is the point: a
    default declared on a contribution is still the default once
    `ScreenRegistry` has it."""
    registry = ContributionRegistry(dev_mode=False)
    _contribute_screens(registry, container=object())

    assert registry.default_route() == "trade"
    assert build_screen_registry(registry).get_default_route() == "trade"


def test_no_view_is_built_while_contributing() -> None:
    """A screen's factory must stay unrun until first navigation — that
    laziness is what keeps boot from importing every screen's dependency
    tree. `container=object()` (not even a `Mock()`) is the proof: a
    factory that ran eagerly would crash on it immediately, since
    `backtest_screen`'s factories call
    `container.resolve(...)`, which a plain `object()` cannot answer."""
    registry = ContributionRegistry(dev_mode=False)
    _contribute_screens(registry, container=object())

    for screen in registry.screens():
        assert callable(screen.view_factory)
        assert callable(screen.presenter_factory)


def test_the_modes_keep_the_sidebars_order() -> None:
    """The mode bar (`EPIC-033C`) lists the screens the sidebar listed, in
    the same order: the first section by item, then the next section."""
    registry = ContributionRegistry(dev_mode=False)
    _contribute_screens(registry, container=object())

    modes = build_screen_registry(registry).modes()

    assert [mode.route for mode in modes] == [
        "market",
        "trade",
        "bots",
        "data_management",
        "backtest",
    ]


def test_the_registry_holds_one_descriptor_per_route() -> None:
    registry = ContributionRegistry(dev_mode=False)
    _contribute_screens(registry, container=object())

    screen_registry = build_screen_registry(registry)
    assert (
        tuple(descriptor.route for descriptor in screen_registry.get_all())
        == _EXPECTED_ROUTES
    )


def test_the_registry_carries_the_commands_contributed_with_the_screens() -> None:
    """`EPIC-033D`: `MainWindow` takes the commands from the same object as
    the screens, so no caller can hand it a desk without the desk's commands
    (the presenter would bind a command that was never contributed)."""
    registry = ContributionRegistry(dev_mode=False)
    _contribute_screens(registry, container=object())

    screen_registry = build_screen_registry(registry)

    assert registry.commands()
    assert tuple(screen_registry.commands()) == tuple(registry.commands())
