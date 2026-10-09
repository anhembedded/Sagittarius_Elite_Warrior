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
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    describe_failure,
    missing_key_failure,
    named_failure_kind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_lookback import (
    require_within_lookback,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)

#: What a read can raise from the SDK or the network.
READ_FAILURES = (BinanceAPIException, BinanceRequestException, RequestException)
#: `EPIC-028Q` — what turning a row into a record can raise when the exchange
#: answers with a row this app cannot read: a missing field, a number that is
#: not one, a value outside an enum.
MAPPING_FAILURES = (KeyError, TypeError, ValueError, ArithmeticError)


def utc_now() -> datetime:
    return datetime.now(UTC)


def from_ms(raw_ms: Any, clock_offset_ms: int = 0) -> datetime:
    """A Binance millisecond timestamp as an aware UTC `datetime` on the
    machine's clock: the exchange's clock less `clock_offset_ms`."""
    return datetime.fromtimestamp((int(raw_ms) - clock_offset_ms) / 1000, tz=UTC)


def order_on_machine_clock[T: Order](order: T, clock_offset_ms: int) -> T:
    """`order` with its `order_time`, which the exchange stamped, moved onto the
    machine's clock like the record around it (`BUG-189`)."""
    if order.order_time is None:
        return order
    return replace(
        order, order_time=order.order_time - timedelta(milliseconds=clock_offset_ms)
    )


def span_ms(
    since: datetime, now: datetime, clock_offset_ms: int = 0
) -> tuple[int, int]:
    """@return `(since, now)` in milliseconds on the exchange's clock, which is
    the machine's plus `clock_offset_ms`.
    @throws ValueError `since` is further back than `MAX_HISTORY_LOOKBACK`."""
    require_within_lookback(since, now)
    return (
        int(since.timestamp() * 1000) + clock_offset_ms,
        int(now.timestamp() * 1000) + clock_offset_ms,
    )


@contextmanager
def history_read_failures(what: str) -> Iterator[None]:
    """Raises `AccountHistoryUnavailableError("<what>: <cause>")` from any
    SDK or network failure inside the block, and from a row the block could
    not map (`"<what>: malformed row: <cause>"`), the cause chained. The error's
    `kind` names the failure when the exchange's answer does (`BUG-181`).

    @details Callers map their rows inside the block (`EPIC-028Q`, the PR
    #300 epic review): a malformed row used to escape the port as a raw
    `KeyError` or `InvalidOperation`."""
    try:
        yield
    except READ_FAILURES as exc:
        raise AccountHistoryUnavailableError(
            f"{what}: {describe_failure(exc)}", named_failure_kind(exc)
        ) from exc
    except MAPPING_FAILURES as exc:
        raise AccountHistoryUnavailableError(f"{what}: malformed row: {exc!r}") from exc


def require_credentials(
    provider: IExchangeCredentialsProvider, venue_label: str
) -> ExchangeCredentials:
    """@throws AccountHistoryUnavailableError No credentials configured, before
    any request is made."""
    resolved = provider.resolve()
    if resolved.credentials is None:
        raise AccountHistoryUnavailableError(
            resolved.unusable_because(venue_label, "read account history"),
            missing_key_failure(resolved),
        )
    return resolved.credentials
