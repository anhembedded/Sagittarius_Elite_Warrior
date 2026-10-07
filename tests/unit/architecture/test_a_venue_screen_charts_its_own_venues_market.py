"""`BUG-172` — a screen that acts on a trading venue reads that venue's own market.

@details Before the fix, one process-wide setting (`exchange.market_data_venue`)
decided the market every chart, stream and backtest read, so Spot Testnet and
Futures Testnet charted mainnet prices while their orders filled on the testnet.
Three halves keep it fixed:

1. **The mapping.** Every venue that places orders names the market-data venue
   of its own environment: a testnet venue a testnet, a mainnet venue the public
   mainnet. A new `TradingVenue` member with no entry fails here, not on screen.
2. **The setting is for screens with no venue.** Only the files below may read
   `ConfigKeys.EXCHANGE_MARKET_DATA_VENUE` or call `resolve_market_data_venue`:
   the declaration, the resolver, the composition that binds the default venue,
   and the Settings page that edits it. A desk, a bot or a backtest started for a
   venue that read it would be the bug again.
3. **A venue screen never takes the default venue's ports.** The desks and the
   Bots screen ask `IMarketDataSources` for their venue's ports; resolving
   `IMarketDataSync`, `IHistoricalKlines`, `IMarketStream`, `IRangeCoverage` or
   `IMarketDataRepository` straight from the container yields the *default*
   venue's, which is the wrong market for two of the four venues.

The composed app's proof, for each of the four venues over the fake exchange, is
`tests/integration/modules/market_data/test_each_venue_charts_from_its_own_market.py`.

Retire when: the setting is deleted and Data mode keeps its own source, or every
screen is a venue screen.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    resolve_testnet_flag,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"

#: The only readers of the setting, by exact path.
_SETTING_READERS = {
    "src/config/config_keys.py",  # the declaration
    "src/support/binance_gateway/contracts/binance_endpoints.py",  # the resolver
    "src/modules/market_data/composition/adapter_bindings.py",  # the default venue
    "src/modules/market_data/ui/settings/market_data_settings_presenter.py",  # edits it
}
_SETTING_NAMES = {"EXCHANGE_MARKET_DATA_VENUE", "resolve_market_data_venue"}

#: The trees whose screens act on a venue.
_VENUE_SCREENS = (
    _SRC / "modules" / "trading" / "ui" / "desk",
    _SRC / "modules" / "bots",
)
_DEFAULT_VENUE_PORTS = {
    "IMarketDataSync",
    "IHistoricalKlines",
    "IMarketStream",
    "IRangeCoverage",
    "IMarketDataRepository",
}


def _names_used(source: str) -> set[str]:
    """Every name read as a variable, an attribute or an import, by `ast`:
    a docstring or a comment that mentions a name is not a use of it."""
    tree = ast.parse(source)
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
        elif isinstance(node, ast.alias):
            used.add(node.name.rsplit(".", 1)[-1])
    return used


def _resolved_types(source: str) -> set[str]:
    """The names passed to a `.resolve(...)` call."""
    resolved: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "resolve"
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            resolved.add(node.args[0].id)
    return resolved


def _python_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


@pytest.mark.parametrize(
    "venue", [venue for venue in TradingVenue if venue.supports_order_submission]
)
def test_every_venues_chart_source_is_its_own_order_environment(
    venue: TradingVenue,
) -> None:
    source = venue.market_data_venue

    assert resolve_testnet_flag(source) is venue.is_testnet
    assert (source is MarketDataVenue.MAINNET_PUBLIC) is venue.is_mainnet


def test_a_venue_that_places_no_orders_has_no_market_to_read() -> None:
    with pytest.raises(ValueError, match="trades no market"):
        TradingVenue.DISABLED.market_data_venue  # noqa: B018 - the property raises


def test_each_testnet_has_its_own_market_data_venue() -> None:
    """Spot's testnet (`testnet.binance.vision`) and Futures' are two exchanges."""
    testnets = [venue for venue in TradingVenue if venue.is_testnet]

    assert len({venue.market_data_venue for venue in testnets}) == len(testnets)


def test_only_the_venueless_screens_read_the_market_data_setting() -> None:
    readers = {
        str(path.relative_to(_REPO_ROOT)).replace("\\", "/")
        for path in _python_files(_SRC)
        if _SETTING_NAMES & _names_used(path.read_text(encoding="utf-8"))
    }

    assert readers == _SETTING_READERS


def test_a_venue_screen_never_resolves_the_default_venues_ports() -> None:
    scanned = [path for root in _VENUE_SCREENS for path in _python_files(root)]
    assert scanned, "the scan found no file: the trees moved and this guard did not"

    offenders = {
        str(path.relative_to(_REPO_ROOT)): sorted(
            _DEFAULT_VENUE_PORTS & _resolved_types(path.read_text(encoding="utf-8"))
        )
        for path in scanned
        if _DEFAULT_VENUE_PORTS & _resolved_types(path.read_text(encoding="utf-8"))
    }

    assert offenders == {}, (
        "a venue screen resolved a port bound to the default market-data venue; "
        "ask `IMarketDataSources.ports_for(venue.market_data_venue)` instead"
    )


def test_the_scanner_sees_a_violation() -> None:
    """Mutation-verify (`testing-rule.md` §2): the scanners fire on the shapes
    they exist for and ignore a name that only a docstring mentions."""
    assert "resolve_market_data_venue" in _names_used(
        "from x import resolve_market_data_venue\n"
    )
    assert "EXCHANGE_MARKET_DATA_VENUE" in _names_used(
        "key = ConfigKeys.EXCHANGE_MARKET_DATA_VENUE\n"
    )
    assert not _SETTING_NAMES & _names_used('"""EXCHANGE_MARKET_DATA_VENUE"""\n')
    assert _resolved_types("c.resolve(IMarketStream)\n") == {"IMarketStream"}
    assert _resolved_types("c.resolve(IMarketDataSources)\n") == {"IMarketDataSources"}
