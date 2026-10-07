"""`BUG-175` — Binance `-2008` (Invalid Api-Key ID) and `-2014` (API-key format
invalid) name the key, not the network.

@details `save_mainnet_key.py spot` answered "Nothing stored: NETWORK" with an
"unclassified exception" error in the log for a testnet key pasted for mainnet,
because only `-2015` was in the classifier's table. The table is shared, so the
Connect step and the Options check get the fix with the script.
"""

from __future__ import annotations

import logging

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    classify_connection_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)


def _api_error(code: int, message: str) -> BinanceAPIException:
    response = type("Response", (), {"status_code": 401, "text": ""})()
    error = BinanceAPIException.__new__(BinanceAPIException)
    error.code, error.message, error.status_code = code, message, 401
    error.response, error.request = response, None
    return error


@pytest.mark.parametrize(
    ("code", "message"),
    [(-2008, "Invalid Api-Key ID."), (-2014, "API-key format invalid.")],
)
def test_an_unknown_or_malformed_key_is_rejected_not_a_network_failure(
    code: int, message: str, caplog
) -> None:
    with caplog.at_level(logging.INFO, logger="App.TradingAdapter"):
        kind = classify_connection_failure(_api_error(code, message), "Spot Mainnet")

    assert kind is ConnectionFailureKind.KEY_REJECTED
    assert "unclassified" not in caplog.text
