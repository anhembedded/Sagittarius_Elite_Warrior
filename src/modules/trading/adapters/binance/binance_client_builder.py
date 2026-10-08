"""`EPIC-034` D11 — the one function that constructs python-binance's `Client` for
a trading venue, testnet or mainnet, Spot or Futures.

@details A mainnet venue is its testnet twin with the endpoint and the key passed
in (D11), so every session is opened the same way: a request timeout, and for a
signed session a clock-corrected `timestamp_offset`. Before this there were four
copies, one per factory method; a fifth was one edit away from disagreeing about
the timeout or the offset. Only the venue differs between calls, and it supplies
both the `testnet` flag and which API family measures the server's clock.

- **Signed** (`credentials` given): the clock offset is measured first (`BUG-111`:
  Binance rejects a signed request more than a second ahead of its own clock, a
  threshold `recvWindow` does not widen, so a machine whose clock merely runs fast
  fails every signed call). Spot measures with `get_server_time()`, Futures with
  `futures_time()`.
- **Unsigned** (`credentials` is `None`): for the public endpoints (`exchangeInfo`,
  `bookTicker`, `premiumIndex`); no key, no measurement.
- **The construction-time ping** is only wanted by a signed Spot session
  (`SpotAccountReader` relies on it, `BUG-045`). A Futures session turns it off
  (`EPIC-028P`): `Client(...)` pings `GET /api/v3/ping`, the Spot API, so every
  Futures session used to reach the Spot venue and a Spot outage failed Futures
  orders before they sent anything. The unsigned Spot session turns it off too:
  the book is read per price-button click, and a ping per read doubled its round
  trips for nothing the read itself does not prove (PR #303 review, finding 1).

It returns the raw `Client`, which has order methods; the factories that call it
type what their callers may reach. `architecture-rule.md` §2: no other file of
`trading` constructs one (`test_only_the_session_factory_constructs_binance_client.py`).
"""

from __future__ import annotations

import logging
import time

from binance.client import Client
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    REQUEST_TIMEOUT_SECONDS,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.TradingAdapter")


def new_client(
    venue: TradingVenue, credentials: ExchangeCredentials | None = None
) -> Client:
    """@raise ValueError `venue` is `DISABLED`: it trades nowhere."""
    market = venue.market_type
    if market is None:
        raise ValueError(f"{venue.name} has no session to open")
    futures = market is MarketType.FUTURES_USD_M
    client = Client(
        api_key=credentials.api_key if credentials else None,
        api_secret=credentials.api_secret if credentials else None,
        requests_params={"timeout": REQUEST_TIMEOUT_SECONDS},
        testnet=venue.is_testnet,
        ping=credentials is not None and not futures,
    )
    if credentials is not None:
        _sync_timestamp_offset(client, futures)
    return client


def _sync_timestamp_offset(client: Client, futures: bool) -> None:
    local_before_ms = int(time.time() * 1000)
    server_time = client.futures_time() if futures else client.get_server_time()
    local_after_ms = int(time.time() * 1000)
    # Midpoint of the round trip is the best available estimate of "local time
    # at the moment the server actually read its own clock".
    local_at_measurement_ms = (local_before_ms + local_after_ms) // 2
    client.timestamp_offset = int(server_time["serverTime"]) - local_at_measurement_ms
    # History reads translate by this offset (`BUG-189`), so a machine whose
    # clock is off is visible in a log that was asked for with `--dev`.
    logger.debug(
        "[clock-offset] %s exchange clock is %d ms from this machine's",
        "futures" if futures else "spot",
        client.timestamp_offset,
    )
