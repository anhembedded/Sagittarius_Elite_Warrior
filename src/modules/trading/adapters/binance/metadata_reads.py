"""`BUG-168` — what both metadata providers do around the `exchangeInfo` call:
the one place an SDK or network failure becomes `SymbolRulesUnavailableError`,
worded by `describe_failure` so an HTML error page never travels up as text."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    describe_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_catalog_unreachable_error import (
    SymbolCatalogUnreachableError,
)

#: What a catalog fetch can raise from the SDK or the network.
_CATALOG_FAILURES = (BinanceAPIException, BinanceRequestException, RequestException)


@contextmanager
def catalog_read_failures(what: str) -> Iterator[None]:
    """@throws SymbolCatalogUnreachableError `"<what> could not be read:
    <reason>"` from any SDK or network failure inside the block, the cause
    chained."""
    try:
        yield
    except _CATALOG_FAILURES as exc:
        raise SymbolCatalogUnreachableError(
            f"{what} could not be read: {describe_failure(exc)}"
        ) from exc
