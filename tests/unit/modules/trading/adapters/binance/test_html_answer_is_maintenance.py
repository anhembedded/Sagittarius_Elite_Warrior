"""EPIC-034D — a Binance answer that is not JSON is the exchange under
maintenance, never an "unclassified exception".

The owner's `-TestnetOnly` run, 2026-10-07: `APIError(code=0): Invalid JSON
error message from Binance: <html>` reached the log as a NETWORK failure with
no name. The real `BinanceAPIException` is built here from a real HTML answer,
so the test fails if the library words the case differently.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    classify_connection_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)

_HTML = "<html><head><title>503 Service Temporarily Unavailable</title></head></html>"


def _answer(text: str, status: int) -> BinanceAPIException:
    return BinanceAPIException(SimpleNamespace(text=text), status, text)


@pytest.mark.parametrize("status", [502, 503, 504, 200])
def test_an_html_answer_is_maintenance(status: int) -> None:
    kind = classify_connection_failure(_answer(_HTML, status), "Spot Testnet")

    assert kind is ConnectionFailureKind.MAINTENANCE


def test_a_json_error_keeps_its_own_kind() -> None:
    exc = _answer('{"code": -2015, "msg": "Invalid API-key"}', 401)

    assert (
        classify_connection_failure(exc, "Spot Testnet")
        is ConnectionFailureKind.KEY_REJECTED
    )


def test_an_unknown_json_code_stays_network() -> None:
    exc = _answer('{"code": -1000, "msg": "unknown"}', 500)

    assert (
        classify_connection_failure(exc, "Spot Testnet")
        is ConnectionFailureKind.NETWORK
    )
