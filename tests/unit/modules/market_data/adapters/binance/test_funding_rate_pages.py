"""`EPIC-039K` — the funding history read, in the shape Binance's page documents.

@details Recorded in the documented shape (`GET /fapi/v1/fundingRate`, read 2026-10-13); not
run against Binance from the sandbox. A record before 2023-11-01 carries no `markPrice`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException, BinanceRequestException
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.funding_rate_pages import (
    PAGE_LIMIT,
    fetch_funding_events,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.funding_event import (
    FundingHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    ExchangeRequestCancelledError,
)

_EIGHT_HOURS_MS = 8 * 3600 * 1000
_START = datetime(2024, 1, 1, tzinfo=UTC)
_START_MS = int(_START.timestamp() * 1000)


def _record(n: int, **extra: Any) -> dict[str, Any]:
    return {
        "symbol": "BTCUSDT",
        "fundingRate": "0.00010000",
        "fundingTime": _START_MS + n * _EIGHT_HOURS_MS,
        "markPrice": "42000.50000000",
        "rateType": "Regular",
    } | extra


def _never() -> bool:
    return False


def test_a_record_becomes_an_event_with_its_rate_time_and_mark_price() -> None:
    sdk = Mock()
    sdk.futures_funding_rate.return_value = [_record(0, fundingRate="-0.00037500")]

    events = fetch_funding_events(
        sdk, "BTCUSDT", _START, datetime(2024, 1, 2, tzinfo=UTC), _never
    )

    assert [(e.time, e.rate, e.mark_price) for e in events] == [
        (_START, Decimal("-0.00037500"), Decimal("42000.50000000"))
    ]
    sdk.futures_funding_rate.assert_called_once_with(
        symbol="BTCUSDT",
        startTime=_START_MS,
        endTime=_START_MS + 24 * 3600 * 1000,
        limit=PAGE_LIMIT,
    )


def test_a_record_from_before_the_mark_price_field_has_no_mark_price() -> None:
    sdk = Mock()
    sdk.futures_funding_rate.return_value = [
        _record(0, markPrice=""),
        {k: v for k, v in _record(1).items() if k != "markPrice"},
    ]

    events = fetch_funding_events(sdk, "BTCUSDT", _START, _START, _never)

    assert [e.mark_price for e in events] == [None, None]


def test_a_full_page_continues_one_millisecond_after_its_last_settlement() -> None:
    first = [_record(n) for n in range(PAGE_LIMIT)]
    second = [_record(PAGE_LIMIT + n) for n in range(3)]
    sdk = Mock()
    sdk.futures_funding_rate.side_effect = [first, second]
    end = datetime(2030, 1, 1, tzinfo=UTC)

    events = fetch_funding_events(sdk, "BTCUSDT", _START, end, _never)

    assert len(events) == PAGE_LIMIT + 3
    assert [e.time for e in events] == sorted(e.time for e in events)
    resumed = sdk.futures_funding_rate.call_args_list[1].kwargs["startTime"]
    assert resumed == first[-1]["fundingTime"] + 1


def test_a_period_with_no_settlement_is_an_empty_history_not_an_error() -> None:
    sdk = Mock()
    sdk.futures_funding_rate.return_value = []

    assert fetch_funding_events(sdk, "BTCUSDT", _START, _START, _never) == []


def test_an_exchange_refusal_is_unavailable_with_the_exchanges_words() -> None:
    sdk = Mock()
    response = Mock(status_code=400, text='{"code": -1121, "msg": "Invalid symbol."}')
    response.json.return_value = {"code": -1121, "msg": "Invalid symbol."}
    sdk.futures_funding_rate.side_effect = BinanceAPIException(
        response, 400, response.text
    )

    with pytest.raises(FundingHistoryUnavailableError) as raised:
        fetch_funding_events(sdk, "NOPEUSDT", _START, _START, _never)

    assert "NOPEUSDT" in raised.value.reason
    assert "Invalid symbol." in raised.value.reason


def test_a_network_failure_is_unavailable() -> None:
    sdk = Mock()
    sdk.futures_funding_rate.side_effect = BinanceRequestException("timed out")

    with pytest.raises(FundingHistoryUnavailableError, match="could not be reached"):
        fetch_funding_events(sdk, "BTCUSDT", _START, _START, _never)


def test_an_answer_in_another_shape_is_unavailable_not_a_wrong_number() -> None:
    sdk = Mock()
    sdk.futures_funding_rate.return_value = [{"symbol": "BTCUSDT", "fundingRate": "x"}]

    with pytest.raises(FundingHistoryUnavailableError, match="cannot read"):
        fetch_funding_events(sdk, "BTCUSDT", _START, _START, _never)


def test_a_cancelled_read_stops_before_asking_the_exchange() -> None:
    sdk = Mock()

    with pytest.raises(ExchangeRequestCancelledError):
        fetch_funding_events(sdk, "BTCUSDT", _START, _START, lambda: True)

    sdk.futures_funding_rate.assert_not_called()
