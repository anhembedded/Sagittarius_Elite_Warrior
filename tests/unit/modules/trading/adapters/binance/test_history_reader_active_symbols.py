"""`BOT-149` — each reader names its active pairs with the reason each is one."""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.active_symbol import (
    ActiveSymbol,
)

from .test_history_readers import _SINCE, _Catalog, _futures, _spot


def _why(pairs: tuple[ActiveSymbol, ...]) -> tuple[tuple[str, str], ...]:
    return tuple((pair.symbol, pair.reason.name) for pair in pairs)


def test_futures_active_symbols_are_open_positions_and_open_orders() -> None:
    client = Mock()
    client.futures_position_information.return_value = [
        {"symbol": "ETHUSDT", "positionAmt": "0.5"},
        {"symbol": "XRPUSDT", "positionAmt": "0"},
        {"symbol": "BTCUSDT", "positionAmt": "-0.01"},
    ]
    client.futures_get_open_orders.return_value = [{"symbol": "SOLUSDT"}]
    # `EPIC-028R` — an open conditional order lives in the Algo Order API.
    client.futures_get_open_algo_orders.return_value = [{"symbol": "DOGEUSDT"}]
    client.futures_income_history.return_value = []

    assert _why(_futures(client).active_symbols(_SINCE)) == (
        ("BTCUSDT", "HELD"),
        ("DOGEUSDT", "OPEN_ORDER"),
        ("ETHUSDT", "HELD"),
        ("SOLUSDT", "OPEN_ORDER"),
    )


def test_futures_active_symbols_include_pairs_traded_since_with_nothing_open() -> None:
    """`EPIC-028Q` — a round trip closed inside the window books income
    (its commission and realized PnL), so its pair is found although nothing
    is open; a transfer, which has no symbol, adds none."""
    client = Mock()
    client.futures_position_information.return_value = []
    client.futures_get_open_orders.return_value = []
    client.futures_get_open_algo_orders.return_value = []
    client.futures_income_history.return_value = [
        {"symbol": "ADAUSDT", "incomeType": "COMMISSION", "income": "-0.01"},
        {"symbol": "ADAUSDT", "incomeType": "REALIZED_PNL", "income": "1.2"},
        {"symbol": "", "incomeType": "TRANSFER", "income": "100"},
    ]

    assert _why(_futures(client).active_symbols(_SINCE)) == (("ADAUSDT", "TRADED"),)
    call = client.futures_income_history.call_args_list[0].kwargs
    assert call["startTime"] == int(_SINCE.timestamp() * 1000)


def test_spot_active_symbols_are_listed_pairs_of_held_assets_and_open_orders() -> None:
    """`DOGE` is held but its pair is not listed; `ETH` is zero; `USDT` is the
    quote asset itself."""
    client = Mock()
    client.get_account.return_value = {
        "balances": [
            {"asset": "BTC", "free": "0.1", "locked": "0"},
            {"asset": "ETH", "free": "0", "locked": "0"},
            {"asset": "BNB", "free": "0", "locked": "2"},
            {"asset": "DOGE", "free": "5", "locked": "0"},
            {"asset": "USDT", "free": "100", "locked": "0"},
        ]
    }
    client.get_open_orders.return_value = [{"symbol": "SOLUSDT"}]

    reader = _spot(client, _Catalog("BTCUSDT", "BNBUSDT", "ETHUSDT", "SOLUSDT"))

    assert _why(reader.active_symbols(_SINCE)) == (
        ("BNBUSDT", "HELD"),
        ("BTCUSDT", "HELD"),
        ("SOLUSDT", "OPEN_ORDER"),
    )


def test_futures_names_a_held_pair_with_an_open_order_once_as_an_open_order() -> None:
    client = Mock()
    client.futures_position_information.return_value = [
        {"symbol": "ETHUSDT", "positionAmt": "0.5"}
    ]
    client.futures_get_open_orders.return_value = [{"symbol": "ETHUSDT"}]
    client.futures_get_open_algo_orders.return_value = []
    client.futures_income_history.return_value = [
        {"symbol": "ETHUSDT", "incomeType": "COMMISSION", "income": "-0.01"}
    ]

    assert _why(_futures(client).active_symbols(_SINCE)) == (("ETHUSDT", "OPEN_ORDER"),)


def test_spot_names_a_held_pair_with_an_open_order_once_as_an_open_order() -> None:
    client = Mock()
    client.get_account.return_value = {
        "balances": [{"asset": "BTC", "free": "0.1", "locked": "0"}]
    }
    client.get_open_orders.return_value = [{"symbol": "BTCUSDT"}]

    reader = _spot(client, _Catalog("BTCUSDT"))

    assert _why(reader.active_symbols(_SINCE)) == (("BTCUSDT", "OPEN_ORDER"),)
