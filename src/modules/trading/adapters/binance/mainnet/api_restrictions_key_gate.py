"""`EPIC-034` D5 — `IKeyPermissionGate` over `GET /sapi/v1/account/apiRestrictions`.

@details Asked before a mainnet venue's key is used for anything: the Connect
step's reader asks it first, and `KeyGatedCredentials` asks it for every other
read and order. A key that can withdraw is refused with `WITHDRAWAL_ENABLED` and
nothing else is read; any other key is
accepted, trading keys included: the owner's decision is that mainnet trades
exactly like testnet (D11). An answer missing the withdrawal flag, or carrying it
as something other than a boolean, refuses the key as unreadable (never a guessed
"cannot withdraw", `code/errors.md` #7).

Verification note: written from python-binance's own source and Binance's
documented API; egress to `*.binance.com` is blocked in this sandbox (HTTP 451),
so it was exercised against the fake Binance server only. The owner's own key is
the live check.

An accepted key is remembered for `ACCEPTED_FOR_SECONDS`, so the order path pays
one request per key per interval; a refusal is never remembered, so the next
call asks again and a key the owner has fixed is taken at once.

Fail closed, except for a key already accepted: a key never judged, or one whose
permissions come back unreadable, is refused; but when the exchange merely does
not answer (unreachable, under maintenance) and this very key was accepted earlier,
that answer stands, so Emergency stop, a cancel and a close are not cut off by an
outage (`EPIC-034` D5). Only an answer from the exchange refuses an accepted key. The standing is in
memory only: a restart starts a key as never judged, on purpose — a persisted
acceptance would outlive the key's permissions.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from decimal import InvalidOperation

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    classify_connection_failure,
    describe_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.key_permissions_client import (
    IKeyPermissionsClient,
    open_key_permissions_client,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.key_permissions_parser import (
    parse_key_permissions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_permission_gate import (
    IKeyPermissionGate,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.KeyGate")

#: How long an accepted key is trusted before the exchange is asked again.
ACCEPTED_FOR_SECONDS = 300.0
_THE_KEY = "the key's permissions"
#: The kinds that say the exchange did not answer, not that it answered about the key.
_NOT_ANSWERING = frozenset(
    {ConnectionFailureKind.NETWORK, ConnectionFailureKind.MAINTENANCE}
)
_NETWORK_FAILURES = (BinanceAPIException, BinanceRequestException, RequestException)
_PARSE_FAILURES = (KeyError, TypeError, ValueError, InvalidOperation)

type KeyPermissionsClients = Callable[
    [TradingVenue, ExchangeCredentials], IKeyPermissionsClient
]
#: What the gate asks for the key to check: the venue's configured key, or a
#: candidate being enrolled. `None` is "no key".
type CredentialsSource = Callable[[], ExchangeCredentials | None]


def _reply(exc: Exception, kind: ConnectionFailureKind) -> str:
    """What the exchange said about the key, for the kinds that are its answer."""
    if kind in _NOT_ANSWERING:
        return ""
    return describe_failure(exc)


class ApiRestrictionsKeyGate(IKeyPermissionGate):
    def __init__(
        self,
        venue: TradingVenue,
        credentials: CredentialsSource,
        clients: KeyPermissionsClients = open_key_permissions_client,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._venue = venue
        self._source = AccountSource.for_venue(venue)
        self._credentials = credentials
        self._clients = clients
        self._clock = clock
        self._lock = threading.Lock()
        #: The key last accepted and when: its identifier only, never the secret.
        self._accepted: tuple[str, float] | None = None

    def check(self) -> ConnectFailure | None:
        resolved = self._credentials()
        if resolved is None:
            return ConnectFailure(self._source, ConnectionFailureKind.NOT_CONFIGURED)
        if self._remembers(resolved):
            return None
        refused, unreachable = self._ask(resolved)
        if refused is not None and unreachable and self._accepted_before(resolved):
            # The exchange did not answer, but this very key was accepted earlier
            # in this session: Emergency stop, a cancel and a close must still go
            # out, so the earlier answer stands for another interval. Only an
            # answer from the exchange ever refuses a key that was accepted.
            logger.info(
                "%s: the key's permissions could not be asked (%s); the key accepted "
                "earlier stands [key-gate]",
                self._venue.display_name,
                refused.kind.value,
            )
            refused = None
        if refused is None:
            with self._lock:
                self._accepted = (resolved.api_key, self._clock())
        return refused

    def _accepted_before(self, key: ExchangeCredentials) -> bool:
        with self._lock:
            accepted = self._accepted
        return accepted is not None and accepted[0] == key.api_key

    def _remembers(self, key: ExchangeCredentials) -> bool:
        with self._lock:
            accepted = self._accepted
        return (
            accepted is not None
            and accepted[0] == key.api_key
            and self._clock() - accepted[1] < ACCEPTED_FOR_SECONDS
        )

    def _ask(self, resolved: ExchangeCredentials) -> tuple[ConnectFailure | None, bool]:
        """The exchange's answer as a refusal (or `None`), and whether the refusal
        is the exchange not answering (unreachable or under maintenance) as
        opposed to an answer about the key."""
        try:
            client = self._clients(self._venue, resolved)
            permissions = parse_key_permissions(client.get_account_api_permissions())
        except _NETWORK_FAILURES as exc:
            kind = classify_connection_failure(exc, self._venue.display_name)
            # A named kind says it all; only the catch-all names the read.
            failure = ConnectFailure(
                self._source,
                kind,
                _THE_KEY if kind is ConnectionFailureKind.NETWORK else "",
                _reply(exc, kind),
            )
            return failure, kind in _NOT_ANSWERING
        except _PARSE_FAILURES as exc:
            logger.warning(
                "%s: %s could not be read: %r [key-gate]",
                self._venue.display_name,
                _THE_KEY,
                exc,
            )
            failure = ConnectFailure(
                self._source, ConnectionFailureKind.NETWORK, _THE_KEY
            )
            return failure, False
        if permissions.can_withdraw:
            logger.warning(
                "%s: the key can withdraw; refused before reading anything [key-gate]",
                self._venue.display_name,
            )
            failure = ConnectFailure(
                self._source, ConnectionFailureKind.WITHDRAWAL_ENABLED, "withdrawals"
            )
            return failure, False
        return None, False
