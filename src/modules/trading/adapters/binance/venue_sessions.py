"""`EPIC-035D` — one signed session per venue and key, opened once and reused.

Every adapter used to open a session for each call: `new_client` pings the
exchange and reads its clock (two requests, `BUG-111`/`BUG-045`) before the one
request the caller wanted, and an order crossed three such opens. A venue now
holds one:

  · opened on first use, and **again** when the key changes (a new session for the
    new key; the old one is dropped, never handed out again), when its clock
    reading is `SESSION_MAX_AGE_SECONDS` old (the offset it measured drifts with
    the machine's clock), or when the open itself failed (a failed open is not kept);
  · the open is a read: it retries, and it stops at a closed gate;
  · shared by every caller of the venue, so the call policy and its gate are too.

The unsigned (public) session opens no network connection and is kept for ever.

Sharing one python-binance `Client` between threads relies on `requests.Session`
being safe for concurrent plain requests, which it is in practice; the client's
`response` attribute (the last answer) is then racy, and only the used-weight
header is read from it, which every answer of the venue carries alike.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.binance_client_builder import (
    new_client,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_policy import (
    SPOT_WEIGHT_LIMIT,
    ExchangeCallPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limit_gate import (
    RateLimitGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.resilient_session import (
    ResilientSession,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: How long a session's clock reading is trusted: ten minutes of drift is far
#: below the second Binance tolerates, and a long-running bot re-measures.
SESSION_MAX_AGE_SECONDS = 600.0
#: Binance's per-minute request weight for a Futures IP.
FUTURES_WEIGHT_LIMIT = 2400

OpenSession = Callable[[TradingVenue, ExchangeCredentials | None], object]


class VenueSessions:
    """One venue's sessions, behind the venue's call policy and gate."""

    def __init__(
        self,
        venue: TradingVenue,
        *,
        policy: ExchangeCallPolicy | None = None,
        open_session: OpenSession = new_client,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._venue = venue
        self._policy = policy or _default_policy(venue)
        self._open_session = open_session
        self._clock = clock
        self._lock = threading.Lock()
        self._signed: tuple[ExchangeCredentials, float, ResilientSession] | None = None
        self._public: ResilientSession | None = None

    @property
    def venue(self) -> TradingVenue:
        return self._venue

    def signed(self, credentials: ExchangeCredentials) -> ResilientSession:
        """The venue's signed session for `credentials`.

        @raise ExchangeRateLimitedError The gate is closed, or the open was limited."""
        with self._lock:
            held = self._signed
            if (
                held is not None
                and held[0] == credentials
                and self._clock() - held[1] < SESSION_MAX_AGE_SECONDS
            ):
                return held[2]
            session = self._opened(credentials)
            self._signed = (credentials, self._clock(), session)
            return session

    def public(self) -> ResilientSession:
        """The venue's unsigned session, for the public endpoints."""
        with self._lock:
            if self._public is None:
                self._public = self._opened(None)
            return self._public

    def _opened(self, credentials: ExchangeCredentials | None) -> ResilientSession:
        client = self._policy.run_read(
            lambda: self._open_session(self._venue, credentials)
        )
        return ResilientSession(client, self._policy)


def _default_policy(venue: TradingVenue) -> ExchangeCallPolicy:
    futures = venue.market_type is MarketType.FUTURES_USD_M
    return ExchangeCallPolicy(
        RateLimitGate(),
        weight_limit=FUTURES_WEIGHT_LIMIT if futures else SPOT_WEIGHT_LIMIT,
    )
