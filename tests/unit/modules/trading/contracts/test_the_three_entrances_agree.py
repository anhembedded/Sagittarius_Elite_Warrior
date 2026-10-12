"""`EPIC-038` D9 — a failure exits the same whether a command meets it as a connection
status, a named order rejection or a raw Binance exception.

The three entrances read one set of codes (`binance_error_codes.py`) and one
mapping (`connection_failure_exit_code.py`); this pins that they cannot drift.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.binance_error_translator import (
    translate_binance_error,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    named_failure_kind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connection_failure_exit_code import (
    EXIT_CODE_FOR_FAILURE,
    exit_code_of_binance_error,
    exit_code_of_order_rejection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_error_codes import (
    BAD_SIGNATURE_CODE,
    CLOCK_SKEW_CODE,
    KEY_REJECTED_CODES,
    OPERATOR_FIXABLE_CODES,
)

_CODES = sorted({*KEY_REJECTED_CODES, BAD_SIGNATURE_CODE, CLOCK_SKEW_CODE, -1003, 0})


def _error(code: int) -> BinanceAPIException:
    response = Mock()
    response.status_code = 400
    response.text = f'{{"code": {code}, "msg": "refused"}}'
    return BinanceAPIException(response, 400, response.text)


@pytest.mark.parametrize("code", _CODES)
def test_a_code_exits_the_same_as_the_connection_failure_it_names(code: int) -> None:
    kind = named_failure_kind(_error(code)) or ConnectionFailureKind.NETWORK

    assert exit_code_of_binance_error(code) is EXIT_CODE_FOR_FAILURE[kind]


@pytest.mark.parametrize("code", sorted(OPERATOR_FIXABLE_CODES))
def test_an_operator_fixable_code_exits_the_same_as_the_order_refused_for_it(
    code: int,
) -> None:
    reason = translate_binance_error(_error(code))

    assert exit_code_of_order_rejection(reason) is exit_code_of_binance_error(code)


def test_only_the_operator_fixable_codes_exit_five() -> None:
    assert {
        c for c in _CODES if exit_code_of_binance_error(c) is ExitCode.CONFIGURATION
    } == (OPERATOR_FIXABLE_CODES)
