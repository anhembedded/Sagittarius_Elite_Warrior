"""The read-only mainnet account has no import path to anything that trades
(`EPIC-034E`, decision D4).

**The rule.** A mainnet key is read, never traded. `AccountSource.SPOT_MAINNET_READONLY`
is not a `TradingVenue` (`EPIC-026` D3 keeps `TradingVenue` free of a mainnet
member), and the code that serves it must not be able to reach a trading
session factory, a trading client, an order-submission port or `execute_order`.
A flag on a trading venue would be the "second path" `EPIC-026` forbids; a type
with no such import makes the wrong state unwritable.

**What is checked.** Every module under `modules/trading/adapters/binance/mainnet/`,
plus the credentials and the read-client port it is built from, is a start. The
walk follows every runtime import (not `TYPE_CHECKING`) through the whole of
`src/`, transitively, and fails when it reaches a module in `FORBIDDEN`. The
failure prints the chain that got there. Two more checks lock the other two
legs: `TradingVenue` has no mainnet member, and the read client's port lists
exactly the reads (a new method is a decision someone must make here).

**What is not checked, honestly.** python-binance's `Client` object has order
methods; the port hides them from the type checker, and this guard keeps the
modules that call them out of reach. A reader that imported `binance.client`
and called `create_order` itself would pass the import walk, which is why the
mainnet reader is typed against `IMainnetReadClient` only and reviewed (E-rows).

Retire when: the read-only mainnet source is deleted, or mainnet becomes a
trading venue by a reviewed decision that supersedes `EPIC-026` D3.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_mainnet_read_client import (
    IMainnetReadClient,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.imports import (
    imported_modules,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"

#: Where the mainnet read-only source lives, and what it is built from.
START_FILES = (
    "support/binance_gateway/contracts/i_mainnet_read_client.py",
    "support/binance_gateway/contracts/i_credentials_resolver.py",
    "support/binance_gateway/contracts/account_source.py",
)

#: What trades, by dotted module name relative to `src/`. A module whose name
#: is one of these, or starts with one followed by a dot, is forbidden.
FORBIDDEN = (
    "modules.trading.adapters.binance.spot.spot_session_factory",
    "modules.trading.adapters.binance.spot.spot_trading_client",
    "modules.trading.adapters.binance.spot.spot_trading_client_factory",
    "modules.trading.adapters.binance.futures_session_factory",
    "modules.trading.adapters.binance.futures_trading_client",
    "modules.trading.adapters.binance.futures_trading_client_factory",
    "support.binance_gateway.contracts.i_spot_session_factory",
    "support.binance_gateway.contracts.i_trading_session_factory",
    "modules.trading.contracts.i_trading_client",
    "modules.trading.contracts.i_trading_client_factory",
    "modules.trading.contracts.i_order_submission",
    "modules.trading.contracts.i_trading_session",
    "modules.trading.application.orders",
    "modules.trading.application.session",
)

#: Every read the mainnet client may make. A new member is a reviewed change.
READS = frozenset(
    {
        "ping",
        "get_server_time",
        "get_account",
        "get_account_api_permissions",
        "get_open_orders",
        "get_orderbook_ticker",
        "get_exchange_info",
    }
)


def is_forbidden(module: str) -> bool:
    return any(module == f or module.startswith(f + ".") for f in FORBIDDEN)


def _file_of(module: str) -> Path | None:
    base = _SRC.joinpath(*module.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _source_in_repo(module: str) -> str | None:
    path = _file_of(module)
    return path.read_text(encoding="utf-8") if path is not None else None


def path_to_an_order(
    starts: list[str], source_of: Callable[[str], str | None]
) -> list[str] | None:
    """The shortest import chain from a start module to a forbidden one, or
    `None`. A module `source_of` cannot read (the engine, the standard
    library) ends the chain: only this repository's modules can trade here."""
    parents: dict[str, str | None] = {start: None for start in starts}
    queue = list(starts)
    while queue:
        module = queue.pop(0)
        if is_forbidden(module):
            return _chain(module, parents)
        source = source_of(module)
        if source is None:
            continue
        for imported in sorted(imported_modules(module, source)):
            if imported not in parents:
                parents[imported] = module
                queue.append(imported)
    return None


def _chain(end: str, parents: dict[str, str | None]) -> list[str]:
    chain = [end]
    while (parent := parents[chain[-1]]) is not None:
        chain.append(parent)
    return chain[::-1]


def _start_modules() -> list[str]:
    files = [_SRC / entry for entry in START_FILES]
    mainnet = _SRC / "modules" / "trading" / "adapters" / "binance" / "mainnet"
    files.extend(sorted(mainnet.glob("*.py")))
    return [
        ".".join(path.relative_to(_SRC).with_suffix("").parts)
        for path in files
        if path.name != "__init__.py"
    ]


def test_the_guard_has_a_subject() -> None:
    starts = _start_modules()

    assert len(starts) > len(START_FILES)  # the directory held modules too
    assert all(_file_of(module) is not None for module in starts)


def test_the_read_only_mainnet_source_reaches_nothing_that_trades() -> None:
    chain = path_to_an_order(_start_modules(), _source_in_repo)

    assert chain is None, (
        "the read-only mainnet source reaches an order: " + " -> ".join(chain or [])
    )


# -- the probe: the walk does find a path when there is one -------------------


def test_the_walk_finds_a_direct_import_of_a_trading_client() -> None:
    graph = {
        "a": "from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import ITradingClient\n",
    }

    assert path_to_an_order(["a"], graph.get) == [
        "a",
        "modules.trading.contracts.i_trading_client",
    ]


def test_the_walk_finds_a_path_through_a_shared_module() -> None:
    graph = {
        "reader": "from Sagittarius_Elite_Warrior.src.shared.helper import h\n",
        "shared.helper": "from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.handler import H\n",
    }

    chain = path_to_an_order(["reader"], graph.get)

    assert chain is not None
    assert chain[0] == "reader"
    assert chain[-1].startswith("modules.trading.application.orders.execute_order")


def test_the_walk_ignores_an_import_only_a_type_checker_sees() -> None:
    graph = {
        "a": (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import C\n"
        ),
    }

    assert path_to_an_order(["a"], graph.get) is None


def test_a_sibling_of_a_forbidden_name_is_not_forbidden() -> None:
    assert not is_forbidden("modules.trading.contracts.i_trading_client_like")
    assert is_forbidden("modules.trading.application.orders.execute_order.handler")


# -- the other two legs -------------------------------------------------------


def test_trading_venue_has_no_mainnet_member() -> None:
    assert not [v.name for v in TradingVenue if "MAINNET" in v.name.upper()]


def test_the_mainnet_source_trades_on_no_venue() -> None:
    source = AccountSource.SPOT_MAINNET_READONLY

    assert source.trading_venue is None
    for venue in TradingVenue:
        if venue is not TradingVenue.DISABLED:
            assert AccountSource.for_venue(venue) is not source


def test_the_read_client_port_lists_exactly_the_reads() -> None:
    members = {
        name
        for name in vars(IMainnetReadClient)
        if not name.startswith("_") and callable(getattr(IMainnetReadClient, name))
    }

    assert members == READS


@pytest.mark.parametrize("name", sorted(READS))
def test_no_read_is_named_like_an_order_call(name: str) -> None:
    placing = ("create_", "cancel_", "new_", "test_", "order_oco")

    assert not name.startswith(placing)
