"""`EPIC-034E` — the checks of `test_mainnet_has_no_order_path.py` do find what
they are there to find: each probe feeds one a path or a call it must catch,
and one it must let by.

Retire when: `test_mainnet_has_no_order_path.py` is."""

from __future__ import annotations

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
from Sagittarius_Elite_Warrior.tests.unit.architecture.order_path_walk import (
    READS,
    SESSION_FACTORY_FILE,
    SRC,
    executed_by,
    is_forbidden,
    order_call_sites,
    path_to_an_order,
)

# -- the probes: each check finds what it is there to find -------------------


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
    assert chain[-1].startswith("modules.trading.application.orders")


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


@pytest.mark.parametrize(
    "call",
    [
        "create_order",
        "create_test_order",
        "cancel_order",
        "cancel_all_open_orders",
        "order_limit_buy",
        "order_oco_sell",
        "create_oco_order",
    ],
)
def test_a_call_that_orders_is_found(call: str) -> None:
    source = f"def f(client):\n    return client.{call}(symbol='BTCUSDT')\n"

    assert order_call_sites(source, "reader.py", may_build_client=False)


@pytest.mark.parametrize(
    "call", ["get_account", "get_open_orders", "get_orderbook_ticker", "ping"]
)
def test_a_read_is_not_taken_for_an_order(call: str) -> None:
    source = f"def f(client):\n    return client.{call}()\n"

    assert order_call_sites(source, "reader.py", may_build_client=False) == []


def test_building_a_client_outside_the_session_factory_is_found() -> None:
    source = "from binance.client import Client\n"

    assert order_call_sites(source, "reader.py", may_build_client=False)
    assert order_call_sites(source, SESSION_FACTORY_FILE, may_build_client=True) == []


def test_the_walk_finds_a_path_through_a_package_init() -> None:
    graph = {
        "reader": "from Sagittarius_Elite_Warrior.src.pkg.contract import C\n",
        "pkg": "from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import T\n",
        "pkg.contract": "",
    }

    chain = path_to_an_order(["reader"], graph.get)

    assert chain is not None
    assert chain[-1] == "modules.trading.contracts.i_trading_client"
    assert "pkg" in chain


def test_the_walk_finds_a_submodule_named_in_a_from_import() -> None:
    graph = {
        "reader": "from Sagittarius_Elite_Warrior.src.modules.trading.contracts import i_trading_client\n"
    }

    chain = path_to_an_order(["reader"], graph.get)

    assert chain == ["reader", "modules.trading.contracts.i_trading_client"]


def test_the_gateway_contracts_package_loads_no_trading_session_port() -> None:
    """Importing any gateway contract runs this `__init__`; the mainnet source
    imports several of them."""
    init = SRC / "support" / "binance_gateway" / "contracts" / "__init__.py"

    assert not [
        module
        for module in executed_by("support.binance_gateway.contracts", init.read_text())
        if is_forbidden(module)
    ]
