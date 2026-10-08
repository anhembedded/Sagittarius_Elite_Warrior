"""`EPIC-035D` — one signed session per venue and key, opened once and reused.

Every adapter used to open a session for each call: `new_client` pings the
exchange and reads its clock (two requests, `BUG-111`/`BUG-045`) before the one
request the caller wanted, and an order crossed three such opens. A venue now
holds one:

  · opened on first use for each key (up to `MAX_SIGNED_SESSIONS` kept, so two
    accounts on one venue do not reopen each other's), and **again** when its
    clock reading is `SESSION_MAX_AGE_SECONDS` old (the offset it measured drifts
    with the machine's clock); a failed open is not kept;
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
#: Signed sessions a venue keeps: one per key in use, oldest dropped first.
MAX_SIGNED_SESSIONS = 4
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
        #: Oldest first; at most `MAX_SIGNED_SESSIONS` keys (two bots on two
        #: accounts of one venue each keep theirs).
        self._signed: dict[ExchangeCredentials, tuple[float, ResilientSession]] = {}
        self._public: ResilientSession | None = None

    @property
    def venue(self) -> TradingVenue:
        return self._venue

    def signed(self, credentials: ExchangeCredentials) -> ResilientSession:
        """The venue's signed session for `credentials`.

        The open runs outside the lock (it pings, reads the clock and may wait
        out a retry): two callers that find no session both open one and the
        later is kept, which costs a request and blocks nobody.

        @raise RateLimitedApiException The gate is closed, or the open was limited."""
        with self._lock:
            held = self._signed.get(credentials)
            if held is not None and self._clock() - held[0] < SESSION_MAX_AGE_SECONDS:
                return held[1]
        session = self._opened(credentials)
        with self._lock:
            self._signed.pop(credentials, None)
            self._signed[credentials] = (self._clock(), session)
            while len(self._signed) > MAX_SIGNED_SESSIONS:
                del self._signed[next(iter(self._signed))]
        return session

    def public(self) -> ResilientSession:
        """The venue's unsigned session, for the public endpoints."""
        with self._lock:
            held = self._public
        if held is not None:
            return held
        session = self._opened(None)
        with self._lock:
            self._public = self._public or session
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
