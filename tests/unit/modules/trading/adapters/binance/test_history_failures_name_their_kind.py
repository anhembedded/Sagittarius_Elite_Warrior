"""`BUG-181` — a history read that fails says *why*, when the exchange does.

@details The Bots screen folds a fills read the venue refused into the Connect
step's one bar, which it can do only if the error carries the same kind the
connection check uses. An answer that names nothing precise (an unknown code, a
network error) carries none, so a screen still tells that failure on its own.
"""

from __future__ import annotations

import pytest
from binance.exceptions import BinanceAPIException, BinanceRequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.history_reads import (
    history_read_failures,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)


def _api_error(code: int, message: str = "refused") -> BinanceAPIException:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code, exc.message = code, message
    exc.status_code, exc.response, exc.request = 401, None, None
    return exc


def _raised_by(failure: Exception) -> AccountHistoryUnavailableError:
    with (
        pytest.raises(AccountHistoryUnavailableError) as caught,
        history_read_failures("order history"),
    ):
        raise failure
    return caught.value


@pytest.mark.parametrize(
    ("code", "kind"),
    [
        (-2015, ConnectionFailureKind.KEY_REJECTED),
        (-2008, ConnectionFailureKind.KEY_REJECTED),
        (-1022, ConnectionFailureKind.BAD_SIGNATURE),
        (-1021, ConnectionFailureKind.CLOCK_SKEW),
    ],
)
def test_a_code_the_exchange_names_gives_the_kind_the_connection_check_uses(
    code: int, kind: ConnectionFailureKind
) -> None:
    assert _raised_by(_api_error(code)).kind is kind


def test_an_html_page_is_maintenance() -> None:
    page = _api_error(0, "Invalid JSON error message from Binance: <html></html>")

    assert _raised_by(page).kind is ConnectionFailureKind.MAINTENANCE


@pytest.mark.parametrize(
    "failure", [_api_error(-1121, "Invalid symbol."), BinanceRequestException("x")]
)
def test_any_other_failure_names_no_kind(failure: Exception) -> None:
    assert _raised_by(failure).kind is None
