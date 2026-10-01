"""`EPIC-028R` — the order CLI commands offer only order types the Futures
client sends without a stop price.

@details `order-preview` and `order-dry-run` take no stop price, so the
stop-limit (sent through Binance's Algo Order API) is not offered, and
`STOP_MARKET`/`TAKE_PROFIT_MARKET`, which no venue sends, are not offered
either. A type added to either side without the other fails here."""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_algo_order_mapper import (
    is_algo_routed,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_order_payload_mapper import (
    FUTURES_SENDABLE_ORDER_TYPES,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.shell.app_config import CLI_COMMANDS_FILE


def _type_choices(command: str) -> list[str]:
    table = json.loads(CLI_COMMANDS_FILE.read_text(encoding="utf-8"))["CLI_COMMANDS"]
    (argument,) = [a for a in table[command]["args"] if a["name"] == "--type"]
    return argument["choices"]


@pytest.mark.parametrize("command", ["order-preview", "order-dry-run"])
def test_every_offered_type_is_one_the_futures_client_sends_without_a_stop(
    command: str,
) -> None:
    choices = _type_choices(command)

    assert choices
    for name in choices:
        order_type = OrderType[name]
        assert order_type in FUTURES_SENDABLE_ORDER_TYPES, name
        assert not is_algo_routed(order_type), name
