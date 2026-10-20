"""`BOT-200` — `CheckKeyQuery` tells a key's venues and keeps nothing: every refusal,
and the success path for each venue."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.check_key import (
    CheckKeyQuery,
    CheckKeyQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_check import (
    KeyCheck,
    KeyCheckRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    KeyEnvironment,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.cli.key_check_world import (
    SENTINEL_KEY,
    SENTINEL_SECRET,
    ScriptedProbe,
    accepted,
    mainnet_accepts,
    refused,
    sentinel_credentials,
    unknown,
    unreachable,
)

_ENV = KeyEnvironment


def _check(
    probe: ScriptedProbe, credentials: ExchangeCredentials | None = None
) -> KeyCheck:
    return CheckKeyQueryHandler(probe).execute(
        CheckKeyQuery(credentials or sentinel_credentials())
    )


@pytest.mark.parametrize(
    ("answers", "venues", "asked"),
    [
        pytest.param(
            {_ENV.MAINNET: mainnet_accepts(spot=True)},
            (TradingVenue.SPOT_MAINNET,),
            [_ENV.MAINNET],
            id="mainnet-spot-only",
        ),
        pytest.param(
            {_ENV.MAINNET: mainnet_accepts(futures=True)},
            (TradingVenue.FUTURES_MAINNET,),
            [_ENV.MAINNET],
            id="mainnet-futures-only",
        ),
        pytest.param(
            {_ENV.MAINNET: mainnet_accepts(spot=True, futures=True)},
            (TradingVenue.SPOT_MAINNET, TradingVenue.FUTURES_MAINNET),
            [_ENV.MAINNET],
            id="mainnet-both",
        ),
        pytest.param(
            {
                _ENV.MAINNET: unknown(_ENV.MAINNET),
                _ENV.SPOT_TESTNET: accepted(_ENV.SPOT_TESTNET),
            },
            (TradingVenue.SPOT_TESTNET,),
            [_ENV.MAINNET, _ENV.SPOT_TESTNET],
            id="spot-testnet",
        ),
        pytest.param(
            {
                _ENV.MAINNET: unknown(_ENV.MAINNET),
                _ENV.SPOT_TESTNET: unknown(_ENV.SPOT_TESTNET),
                _ENV.FUTURES_TESTNET: accepted(_ENV.FUTURES_TESTNET),
            },
            (TradingVenue.FUTURES_TESTNET,),
            [_ENV.MAINNET, _ENV.SPOT_TESTNET, _ENV.FUTURES_TESTNET],
            id="futures-testnet",
        ),
    ],
)
def test_an_accepted_key_is_for_the_venues_its_environment_and_permissions_allow(
    answers, venues, asked
) -> None:
    probe = ScriptedProbe(answers)

    check = _check(probe)

    assert check.refusal is None
    assert check.venues == venues
    assert probe.asked == asked, "asking stops at the first environment that accepts"


def test_a_mainnet_key_that_can_withdraw_is_refused_whatever_else_it_can_do() -> None:
    check = _check(
        ScriptedProbe({_ENV.MAINNET: mainnet_accepts(spot=True, withdraw=True)})
    )

    assert check.refusal is KeyCheckRefusal.WITHDRAWAL_ENABLED
    assert check.venues == ()


def test_a_mainnet_key_that_may_trade_nothing_is_refused() -> None:
    check = _check(ScriptedProbe({_ENV.MAINNET: mainnet_accepts()}))

    assert check.refusal is KeyCheckRefusal.NO_TRADING_PERMISSION
    assert check.venues == ()


def test_a_key_no_environment_accepts_is_refused_with_every_reason() -> None:
    probe = ScriptedProbe(
        {
            _ENV.MAINNET: unknown(_ENV.MAINNET),
            _ENV.SPOT_TESTNET: refused(_ENV.SPOT_TESTNET),
            _ENV.FUTURES_TESTNET: unreachable(_ENV.FUTURES_TESTNET),
        }
    )

    check = _check(probe)

    assert check.refusal is KeyCheckRefusal.NOT_ACCEPTED
    assert [v.environment for v in check.verdicts] == list(KeyEnvironment)
    assert probe.asked == list(KeyEnvironment)


@pytest.mark.parametrize(
    "credentials",
    [
        ExchangeCredentials("", SENTINEL_SECRET),
        ExchangeCredentials(SENTINEL_KEY, ""),
        ExchangeCredentials("   ", SENTINEL_SECRET),
        ExchangeCredentials(SENTINEL_KEY, "\t"),
    ],
)
def test_an_empty_key_or_secret_asks_the_exchange_nothing(credentials) -> None:
    probe = ScriptedProbe({})

    check = _check(probe, credentials)

    assert check.refusal is KeyCheckRefusal.INCOMPLETE
    assert probe.asked == []


@pytest.mark.parametrize(
    "credentials",
    [
        ExchangeCredentials(SENTINEL_KEY + " ", SENTINEL_SECRET),
        ExchangeCredentials(SENTINEL_KEY, "SENTINEL SECRET"),
        ExchangeCredentials(SENTINEL_KEY + "é", SENTINEL_SECRET),
        ExchangeCredentials(SENTINEL_KEY, SENTINEL_SECRET + "\x00"),
        ExchangeCredentials(SENTINEL_KEY + "\r", SENTINEL_SECRET),
    ],
)
def test_a_character_a_binance_key_never_has_is_refused_before_asking(
    credentials,
) -> None:
    probe = ScriptedProbe({_ENV.MAINNET: mainnet_accepts(spot=True)})

    check = _check(probe, credentials)

    assert check.refusal is KeyCheckRefusal.NOT_A_KEY
    assert probe.asked == []
