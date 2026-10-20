"""`BOT-200` — the one place a key is told apart: which venues is it for?

@details Asks each environment in turn and stops at the first that accepts the key
(a key is valid in exactly one), then decides the venues from what the exchange says
the key may do. `EnrolKeyCommandHandler` keeps the key for those venues; the
`CheckKeyQuery` only reports them. Both read this function, so adding a key on the
Options page and checking one at the command line cannot disagree about a key.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_environment_probe import (
    IKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_check import (
    KeyCheck,
    KeyCheckRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
    KeyEnvironment,
    KeyStanding,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_TESTNET_VENUES = {
    KeyEnvironment.SPOT_TESTNET: TradingVenue.SPOT_TESTNET,
    KeyEnvironment.FUTURES_TESTNET: TradingVenue.FUTURES_TESTNET,
}


def classify_key(
    probe: IKeyEnvironmentProbe, credentials: ExchangeCredentials
) -> KeyCheck:
    if not credentials.api_key.strip() or not credentials.api_secret.strip():
        return KeyCheck((), refusal=KeyCheckRefusal.INCOMPLETE)
    if not (credentials.api_key.isascii() and credentials.api_secret.isascii()):
        return KeyCheck((), refusal=KeyCheckRefusal.NOT_A_KEY)

    verdicts: list[EnvironmentVerdict] = []
    accepted: EnvironmentVerdict | None = None
    for environment in KeyEnvironment:
        verdict = probe.probe(environment, credentials)
        verdicts.append(verdict)
        if verdict.standing is KeyStanding.ACCEPTED:
            accepted = verdict
            break
    if accepted is None:
        return KeyCheck((), tuple(verdicts), KeyCheckRefusal.NOT_ACCEPTED)

    decided = _venues_for(accepted)
    if isinstance(decided, KeyCheckRefusal):
        return KeyCheck((), tuple(verdicts), decided)
    return KeyCheck(decided, tuple(verdicts))


def _venues_for(
    accepted: EnvironmentVerdict,
) -> tuple[TradingVenue, ...] | KeyCheckRefusal:
    if accepted.environment is not KeyEnvironment.MAINNET:
        return (_TESTNET_VENUES[accepted.environment],)
    permissions = accepted.permissions
    if permissions is None or permissions.can_withdraw:
        return KeyCheckRefusal.WITHDRAWAL_ENABLED
    venues = tuple(
        venue
        for venue, allowed in (
            (TradingVenue.SPOT_MAINNET, permissions.can_trade_spot),
            (TradingVenue.FUTURES_MAINNET, permissions.can_trade_futures),
        )
        if allowed
    )
    return venues or KeyCheckRefusal.NO_TRADING_PERMISSION
