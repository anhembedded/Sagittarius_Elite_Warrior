"""`EPIC-034` D5 — `IKeyPermissionGate` over `GET /sapi/v1/account/apiRestrictions`.

@details Asked before any account read of a mainnet venue. A key that can withdraw
is refused with `WITHDRAWAL_ENABLED` and nothing else is read; any other key is
accepted, trading keys included: the owner's decision is that mainnet trades
exactly like testnet (D11). An answer missing the withdrawal flag, or carrying it
as something other than a boolean, refuses the key as unreadable (never a guessed
"cannot withdraw", `code/errors.md` #7).

Verification note: written from python-binance's own source and Binance's
documented API; egress to `*.binance.com` is blocked in this sandbox (HTTP 451),
so it was exercised against the fake Binance server only. The owner's own key is
the live check.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from decimal import InvalidOperation

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    classify_connection_failure,
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

_THE_KEY = "the key's permissions"
_NETWORK_FAILURES = (BinanceAPIException, BinanceRequestException, RequestException)
_PARSE_FAILURES = (KeyError, TypeError, ValueError, InvalidOperation)

type KeyPermissionsClients = Callable[
    [TradingVenue, ExchangeCredentials], IKeyPermissionsClient
]
#: What the gate asks for the key to check: the venue's configured key, or a
#: candidate being enrolled. `None` is "no key".
type CredentialsSource = Callable[[], ExchangeCredentials | None]


class ApiRestrictionsKeyGate(IKeyPermissionGate):
    def __init__(
        self,
        venue: TradingVenue,
        credentials: CredentialsSource,
        clients: KeyPermissionsClients = open_key_permissions_client,
    ) -> None:
        self._venue = venue
        self._source = AccountSource.for_venue(venue)
        self._credentials = credentials
        self._clients = clients

    def check(self) -> ConnectFailure | None:
        resolved = self._credentials()
        if resolved is None:
            return ConnectFailure(self._source, ConnectionFailureKind.NOT_CONFIGURED)
        try:
            client = self._clients(self._venue, resolved)
            permissions = parse_key_permissions(client.get_account_api_permissions())
        except _NETWORK_FAILURES as exc:
            kind = classify_connection_failure(exc, self._venue.display_name)
            # A named kind says it all; only the catch-all names the read.
            return ConnectFailure(
                self._source,
                kind,
                _THE_KEY if kind is ConnectionFailureKind.NETWORK else "",
            )
        except _PARSE_FAILURES as exc:
            logger.warning(
                "%s: %s could not be read: %r [key-gate]",
                self._venue.display_name,
                _THE_KEY,
                exc,
            )
            return ConnectFailure(self._source, ConnectionFailureKind.NETWORK, _THE_KEY)
        if permissions.can_withdraw:
            logger.warning(
                "%s: the key can withdraw; refused before reading anything [key-gate]",
                self._venue.display_name,
            )
            return ConnectFailure(
                self._source, ConnectionFailureKind.WITHDRAWAL_ENABLED, "withdrawals"
            )
        return None
