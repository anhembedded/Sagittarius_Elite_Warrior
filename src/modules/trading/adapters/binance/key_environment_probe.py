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

How the exchange's refusal is told: the shared `connection_failure.py` classifier
files `-2008`, `-2014` and `-2015` under `KEY_REJECTED`; `UNKNOWN_KEY_CODES`, held
there, says which of them mean this environment does not know the key (`-2008`,
`-2014`) as against knowing it and refusing this request (`-2015`: an IP off the
allowlist or a missing permission). Every failure carries `describe_failure`'s
words, the exchange's code and message then the reason and the fixes, so this page,
a log line and the Connect step say one thing; a maintenance page, a clock fault or
a dead network is told as it is everywhere else.

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
    UNKNOWN_KEY_CODES,
    classify_connection_failure,
    describe_failure,
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
        # `-2008`/`-2014`: this environment does not know the key; `-2015`: it
        # knows it and refuses the request (`connection_failure.py` holds the codes).
        unknown = isinstance(exc, BinanceAPIException) and exc.code in UNKNOWN_KEY_CODES
        return EnvironmentVerdict(
            environment,
            KeyStanding.UNKNOWN if unknown else KeyStanding.REFUSED,
            reason=describe_failure(exc),
        )
    return EnvironmentVerdict(
        environment, KeyStanding.UNREACHABLE, failure=kind, reason=describe_failure(exc)
    )
