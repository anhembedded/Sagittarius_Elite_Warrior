"""`EPIC-028O` — `symbolConfig` and `leverageBracket` answers become the
port's value types, for the asked symbol only."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_settings_parser import (
    parse_leverage_brackets,
    parse_symbol_setting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)


def _config(symbol: str, leverage: int, margin: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "marginType": margin,
        "isAutoAddMargin": "false",
        "leverage": leverage,
        "maxNotionalValue": "1000000",
    }


def _entry(symbol: str, *caps: int) -> dict[str, Any]:
    floors = (0, *caps[:-1])
    return {
        "symbol": symbol,
        "notionalCoef": 1.5,
        "brackets": [
            {
                "bracket": number,
                "initialLeverage": 125 // number,
                "notionalCap": cap,
                "notionalFloor": floor,
                "maintMarginRatio": 0.004 * number,
                "cum": 0.0 if number == 1 else 10.0 * number,
            }
            for number, (floor, cap) in enumerate(zip(floors, caps, strict=True), 1)
        ],
    }


def test_the_asked_symbols_row_is_read() -> None:
    answer = [_config("ETHUSDT", 5, "CROSSED"), _config("BTCUSDT", 21, "ISOLATED")]

    setting = parse_symbol_setting(answer, "BTCUSDT")

    assert setting == FuturesSymbolSetting(
        "BTCUSDT", 21, MarginType.ISOLATED, Decimal(1_000_000)
    )


def test_a_setting_answer_without_the_symbol_is_unreadable() -> None:
    with pytest.raises(KeyError, match="BTCUSDT"):
        parse_symbol_setting([_config("ETHUSDT", 5, "CROSSED")], "BTCUSDT")


def test_an_unknown_margin_type_is_unreadable() -> None:
    with pytest.raises(ValueError, match="'portfolio'"):
        parse_symbol_setting([_config("BTCUSDT", 5, "PORTFOLIO")], "BTCUSDT")


@pytest.mark.parametrize(
    "answer",
    [
        _entry("BTCUSDT", 50_000, 500_000),
        [_entry("ETHUSDT", 10_000, 100_000), _entry("BTCUSDT", 50_000, 500_000)],
    ],
    ids=["one-symbol-object", "list-of-symbols"],
)
def test_brackets_are_read_from_either_answer_shape(
    answer: dict[str, Any] | list[dict[str, Any]],
) -> None:
    brackets = parse_leverage_brackets(answer, "BTCUSDT")

    assert brackets.symbol == "BTCUSDT"
    assert [b.notional_cap for b in brackets.brackets] == [50_000, 500_000]
    assert brackets.brackets[1].maintenance_margin_rate == Decimal("0.008")
    assert brackets.brackets[1].maintenance_amount == 20


def test_brackets_listed_out_of_order_are_sorted_by_notional() -> None:
    entry = _entry("BTCUSDT", 50_000, 500_000)
    entry["brackets"].reverse()

    brackets = parse_leverage_brackets(entry, "BTCUSDT")

    assert [b.bracket for b in brackets.brackets] == [1, 2]


def test_a_bracket_answer_for_another_symbol_is_unreadable() -> None:
    with pytest.raises(KeyError, match="BTCUSDT"):
        parse_leverage_brackets(_entry("ETHUSDT", 10_000), "BTCUSDT")
