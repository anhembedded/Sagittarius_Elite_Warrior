"""`EPIC-039K` — `GET /fapi/v1/fundingRate`, paged until a period is covered.

@details Binance's page (read 2026-10-13): public, `symbol`, `startTime` and `endTime` (ms,
both inclusive), `limit` (default 100, at most 1000); the answer is oldest first, an array of
`{symbol, fundingRate, fundingTime, markPrice, rateType}`. When the period holds more than
`limit` records the answer starts at `startTime`, so the next page starts one millisecond
after the last `fundingTime` seen. `markPrice` exists only on records from 2023-11-01 on;
`rateType` is `Regular`, or `Special` for the extra settlement stock-dividend perpetuals
get — a charge like any other, so both are returned. The endpoint shares a 500 requests per
5 minutes per IP limit with `fundingInfo`; a period is one request per 1000 settlements
(about a year of a three-a-day symbol).

Not run against Binance from the build sandbox (egress to `*.binance.*` is blocked); the
tests feed recorded answers in this shape.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

import requests
from binance.exceptions import BinanceAPIException, BinanceRequestException
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.funding_event import (
    FundingEvent,
    FundingHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    ExchangeRequestCancelledError,
)

logger = logging.getLogger("App.FundingRatePages")

#: Binance's largest page; a shorter answer is the last one.
PAGE_LIMIT = 1000


class FundingRateEndpoint(Protocol):
    """The one call this reads: python-binance's `Client.futures_funding_rate`.

    @details A `Protocol` for reason (c) of `architecture-rule.md` §2.1: the implementer is
    a third-party class (`binance.client.Client`)."""

    def futures_funding_rate(self, **params: object) -> list[dict[str, Any]]: ...


def fetch_funding_events(
    client: FundingRateEndpoint,
    symbol: str,
    start: datetime,
    end: datetime,
    cancelled: Callable[[], bool],
) -> list[FundingEvent]:
    """The settlements of `symbol` with `start <= time <= end`, oldest first."""
    events: list[FundingEvent] = []
    cursor = _milliseconds(start)
    last = _milliseconds(end)
    while cursor <= last:
        if cancelled():
            raise ExchangeRequestCancelledError("Funding history request cancelled")
        page = _page(client, symbol, cursor, last)
        events.extend(_event(record, symbol) for record in page)
        if len(page) < PAGE_LIMIT:
            break
        cursor = int(page[-1]["fundingTime"]) + 1
    logger.info(
        "[funding-history] %s %s..%s: %d settlements",
        symbol,
        start.isoformat(),
        end.isoformat(),
        len(events),
    )
    return events


def _page(
    client: FundingRateEndpoint, symbol: str, start_ms: int, end_ms: int
) -> list[dict[str, Any]]:
    try:
        return client.futures_funding_rate(
            symbol=symbol, startTime=start_ms, endTime=end_ms, limit=PAGE_LIMIT
        )
    except BinanceAPIException as exc:
        raise FundingHistoryUnavailableError(
            f"The exchange refused the funding history of {symbol}: {exc.message}"
        ) from exc
    except (BinanceRequestException, requests.RequestException) as exc:
        raise FundingHistoryUnavailableError(
            f"The exchange could not be reached for the funding history of {symbol}."
        ) from exc


def _event(record: dict[str, Any], symbol: str) -> FundingEvent:
    try:
        mark = str(record.get("markPrice") or "")
        return FundingEvent(
            symbol=symbol,
            time=datetime.fromtimestamp(int(record["fundingTime"]) / 1000, tz=UTC),
            rate=Decimal(str(record["fundingRate"])),
            mark_price=Decimal(mark) if mark else None,
        )
    except (KeyError, ValueError, InvalidOperation) as exc:
        raise FundingHistoryUnavailableError(
            f"The funding history of {symbol} came in a shape this cannot read: {record!r}"
        ) from exc


def _milliseconds(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)
