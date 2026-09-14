"""The verified fake for `IMarketDataSync` (HLD §10.3).

**Who needs it.** Four screens ask for a sync and then read the store. Their
tests need a sync they can assert against without a network or a database —
and, since `IMarketDataSync` is a *foreign* port to every one of them,
`Mock(spec=IMarketDataSync)` is not an option: `test_no_foreign_port_is_mocked.py`
fails on it, because a mock agrees with whatever the test asserts and cannot
notice the day the port's real behaviour changes.

**What it does and does not do.** It records requests and applies the two rules
the port promises before a request reaches storage — an empty symbol list is
rejected, symbols are upper-cased, a missing correlation id is generated. It
fetches nothing: a test that needs candles to come back seeds
`FakeMarketDataRepository`, which is the pair a consumer normally holds
(*ask for a sync, then read the store*).

That division is the honest one. This fake cannot pretend to fetch, because
what the real sync writes depends on an exchange; what it *can* guarantee is
the contract every implementation shares, which is what
`contract_market_data_sync.py` pins for both of them.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
    MarketDataSyncRequest,
)


class FakeMarketDataSync(IMarketDataSync):
    """Every sync that was asked for, in order, and nothing fetched."""

    def __init__(self) -> None:
        #: Each accepted request, normalised exactly as the real path
        #: normalises it. A consumer asserts against this instead of against
        #: "was a command dispatched", which is what a `Mock` would have
        #: forced it to assert.
        self.requests: list[MarketDataSyncRequest] = []

    def sync(self, request: MarketDataSyncRequest) -> None:
        if not request.symbols:
            # Same refusal, same place: `SyncMarketDataCommand`'s validator
            # raises on an empty list, so a consumer that builds a request
            # from an empty selection sees the failure in a test rather than
            # in production.
            raise ValueError("Symbols list cannot be empty")

        self.requests.append(
            replace(
                request,
                symbols=tuple(symbol.upper() for symbol in request.symbols),
                correlation_id=request.correlation_id or uuid.uuid4().hex,
            )
        )

    # -- what a consumer's test usually wants to know ------------------------

    @property
    def synced_symbols(self) -> list[str]:
        """Every symbol asked for, across all requests, in order."""
        return [symbol for request in self.requests for symbol in request.symbols]

    def was_asked_for(self, symbol: str, interval: object | None = None) -> bool:
        """Whether any request named this symbol (optionally at one interval).

        Spelled as a question rather than leaving every consumer to write the
        same comprehension over `requests`, and case-insensitive because the
        port's own promise is that case does not matter.
        """
        wanted = symbol.upper()
        return any(
            wanted in request.symbols
            and (interval is None or request.interval == interval)
            for request in self.requests
        )
