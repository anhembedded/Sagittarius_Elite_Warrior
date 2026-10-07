"""`BUG-176` — `IKeyEnvironmentProbe` over the three places a Binance key can live.

@details One signed read of the account per environment, the same read that
environment's connection check makes, so a key this accepts is a key the
connection check then accepts:

- **mainnet** — `GET /sapi/v1/account/apiRestrictions` through a Spot mainnet
  session. It answers for the key whichever market it trades and says what the
  key may do (`KeyPermissions`), so it is the only environment whose verdict
  carries permissions.
- **Spot Testnet** — `GET /api/v3/account`.
- **Futures Testnet** — `GET /fapi/v2/account` (testnet.binancefuture.com, the
  endpoint python-binance's `testnet=True` selects for the Futures venue).

How the exchange's refusal is told: `-2008` (unknown key) and `-2014` (bad key
format) mean this environment does not know the key; `-2015` (the shared
`connection_failure.py` table's `KEY_REJECTED`) means it knows the key and refuses
this request, an IP off the allowlist or a missing permission. The two codes for an
unknown key are named here because the shared table still files them under the
catch-all; everything else is the shared classifier's answer, so a maintenance
page, a clock fault or a dead network is told as it is everywhere else.

Verification note: the codes are written from Binance's documented errors and the
owner's logs (`BUG-175`), not re-checked against a live call; egress to
`*.binance.*` is blocked in this sandbox. The fake Binance server proves the paths.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.binance_client_builder import (
    new_client,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    classify_connection_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.key_permissions_parser import (
    parse_key_permissions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_environment_probe import (
    IKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
    KeyEnvironment,
    KeyStanding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_key import (
    key_fingerprint,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.KeyProbe")

#: Binance codes for "this environment has no such key": `-2008` Invalid Api-Key ID,
#: `-2014` API-key format invalid.
_UNKNOWN_KEY_CODES = frozenset({-2008, -2014})
_ANSWER_FAILURES = (
    BinanceAPIException,
    BinanceRequestException,
    RequestException,
    KeyError,
    TypeError,
    ValueError,
)

#: The session each environment is asked through. Mainnet asks through Spot's host,
#: which serves `apiRestrictions` for a key of either market.
_SESSION_VENUES: dict[KeyEnvironment, TradingVenue] = {
    KeyEnvironment.MAINNET: TradingVenue.SPOT_MAINNET,
    KeyEnvironment.SPOT_TESTNET: TradingVenue.SPOT_TESTNET,
    KeyEnvironment.FUTURES_TESTNET: TradingVenue.FUTURES_TESTNET,
}

type _Opener = Callable[[TradingVenue, ExchangeCredentials], Any]


class BinanceKeyEnvironmentProbe(IKeyEnvironmentProbe):
    def __init__(self, open_session: _Opener = new_client) -> None:
        self._open_session = open_session

    def probe(
        self, environment: KeyEnvironment, credentials: ExchangeCredentials
    ) -> EnvironmentVerdict:
        try:
            verdict = self._ask(environment, credentials)
        except _ANSWER_FAILURES as exc:
            verdict = _verdict_of_failure(environment, exc)
        logger.info(
            "%s: the key %s was %s [key-probe]",
            environment.label,
            key_fingerprint(credentials.api_key),
            verdict.standing.value,
        )
        return verdict

    def _ask(
        self, environment: KeyEnvironment, credentials: ExchangeCredentials
    ) -> EnvironmentVerdict:
        session = self._open_session(_SESSION_VENUES[environment], credentials)
        if environment is KeyEnvironment.MAINNET:
            permissions = parse_key_permissions(session.get_account_api_permissions())
            return EnvironmentVerdict(
                environment, KeyStanding.ACCEPTED, permissions=permissions
            )
        if environment is KeyEnvironment.SPOT_TESTNET:
            session.get_account()
        else:
            session.futures_account()
        return EnvironmentVerdict(environment, KeyStanding.ACCEPTED)


def _verdict_of_failure(
    environment: KeyEnvironment, exc: Exception
) -> EnvironmentVerdict:
    if isinstance(exc, BinanceAPIException) and exc.code in _UNKNOWN_KEY_CODES:
        return EnvironmentVerdict(environment, KeyStanding.UNKNOWN)
    if isinstance(exc, KeyError | TypeError | ValueError):
        # An answer that is not what the exchange documents: not an answer about
        # the key, so never read as accepted or refused (`code/errors.md` #7).
        # The exception's type only: `requests` puts the key itself in a
        # `UnicodeEncodeError`'s text when the key has a character it cannot send.
        logger.warning(
            "%s: the answer could not be read (%s) [key-probe]",
            environment.label,
            type(exc).__name__,
        )
        return EnvironmentVerdict(
            environment, KeyStanding.UNREACHABLE, failure=ConnectionFailureKind.NETWORK
        )
    kind = classify_connection_failure(exc, environment.label)
    if kind is ConnectionFailureKind.KEY_REJECTED:
        return EnvironmentVerdict(environment, KeyStanding.REFUSED)
    return EnvironmentVerdict(environment, KeyStanding.UNREACHABLE, failure=kind)
