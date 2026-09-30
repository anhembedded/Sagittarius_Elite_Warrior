"""`EPIC-028E` — what both history readers do around the exchange.

@details `FuturesHistoryReader` and `SpotHistoryReader` differ in endpoints,
limits and payloads, and share everything else here: the span a read may
cover, the conversion to Binance's millisecond timestamps, the credential
check, and the one place an SDK or network failure becomes
`AccountHistoryUnavailableError` (the PR #297 review, findings 1 and 5).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    MAX_HISTORY_LOOKBACK,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)

#: What a read can raise from the SDK or the network.
READ_FAILURES = (BinanceAPIException, BinanceRequestException, RequestException)


def utc_now() -> datetime:
    return datetime.now(UTC)


def from_ms(raw_ms: Any) -> datetime:
    """A Binance millisecond timestamp as an aware UTC `datetime`."""
    return datetime.fromtimestamp(int(raw_ms) / 1000, tz=UTC)


def span_ms(since: datetime, now: datetime) -> tuple[int, int]:
    """@return `(since, now)` in milliseconds.
    @throws ValueError `since` is further back than `MAX_HISTORY_LOOKBACK`."""
    if now - since > MAX_HISTORY_LOOKBACK:
        raise ValueError(
            f"since {since.isoformat()} is more than {MAX_HISTORY_LOOKBACK.days} "
            "days back; read a shorter span"
        )
    return int(since.timestamp() * 1000), int(now.timestamp() * 1000)


@contextmanager
def history_read_failures(what: str) -> Iterator[None]:
    """Raises `AccountHistoryUnavailableError("<what>: <cause>")` from any
    SDK or network failure inside the block, the cause chained."""
    try:
        yield
    except READ_FAILURES as exc:
        raise AccountHistoryUnavailableError(f"{what}: {exc}") from exc


def require_credentials(
    provider: IExchangeCredentialsProvider, venue_label: str
) -> ExchangeCredentials:
    """@throws AccountHistoryUnavailableError No credentials configured, before
    any request is made."""
    credentials = provider.resolve().credentials
    if credentials is None:
        raise AccountHistoryUnavailableError(
            f"No {venue_label} credentials configured — cannot read account history."
        )
    return credentials
