"""`BUG-176` — adding a key finds the environment it belongs to, over the fake Binance.

@details Three fake exchanges run at once — mainnet, Spot Testnet and Futures
Testnet — each knowing a different set of keys, with python-binance's four hosts
pointed at them. The real probe, the real `EnrolKeyCommandHandler` and each venue's
real credentials provider (a temp `secrets.local.json` for the testnets, an in-memory
store standing in for the keyring for the mainnets) run unchanged.

No `*.binance.com` host is reached and nothing here places an order: the probe makes
one signed read per environment, and `_nothing_was_placed` checks the servers' logs.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.key_environment_probe import (
    BinanceKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.credentials.enrol_key import (
    EnrolKeyCommand,
    EnrolKeyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_enrolment import (
    EnrolmentRefusal,
    KeyEnrolment,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    KeyEnvironment,
    KeyStanding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.tests.integration.infrastructure.binance.fake_key_world import (
    FUTURES_MAINNET,
    FUTURES_TESTNET,
    KEY,
    OLD_FUTURES_TESTNET_KEY,
    OLD_SPOT_MAINNET_KEY,
    PLACING,
    SECRET,
    SPOT_MAINNET,
    SPOT_TESTNET,
    World,
    build_world,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import (
    InMemorySecretStore,
    UnavailableSecretStore,
)


@pytest.fixture(autouse=True)
def _no_environment_keys(monkeypatch: pytest.MonkeyPatch) -> None:

    for name in list(os.environ):
        if name.startswith("BINANCE_"):
            monkeypatch.delenv(name)


@pytest.fixture
def world(tmp_path: Path) -> Iterator[World]:
    """Every environment knows no key until a test says which it knows."""
    yield from build_world(tmp_path, InMemorySecretStore())


def _everything_unknown(world: World) -> None:
    for server in world.servers():
        server.keys.known = set()


def _nothing_was_placed(world: World) -> None:
    for server in world.servers():
        assert not [r for r in server.requests if r[0] in PLACING]


def _standing(result: KeyEnrolment) -> dict[KeyEnvironment, KeyStanding]:
    return {v.environment: v.standing for v in result.verdicts}


def test_a_key_unknown_everywhere_is_stored_nowhere_and_each_environment_says_so(
    world: World,
) -> None:
    _everything_unknown(world)

    result = world.enrol()

    assert result.refusal is EnrolmentRefusal.NOT_ACCEPTED
    assert result.stored == ()
    assert _standing(result) == dict.fromkeys(KeyEnvironment, KeyStanding.UNKNOWN)
    assert [world.key_of(v) for v in world.providers] == [None] * 4
    assert world.keyring.secrets == {}
    assert not world.secrets_file.exists()
    _nothing_was_placed(world)


def test_a_key_mainnet_knows_but_refuses_is_told_apart_from_an_unknown_one(
    world: World,
) -> None:
    """`-2015`: the key exists on mainnet and the request was refused (an IP off the
    key's allowlist, a missing permission) — not "wrong environment"."""
    _everything_unknown(world)
    world.mainnet.keys.known = {KEY}
    world.mainnet.keys.refused = {KEY}

    result = world.enrol()

    assert result.refusal is EnrolmentRefusal.NOT_ACCEPTED
    assert _standing(result) == {
        KeyEnvironment.MAINNET: KeyStanding.REFUSED,
        KeyEnvironment.SPOT_TESTNET: KeyStanding.UNKNOWN,
        KeyEnvironment.FUTURES_TESTNET: KeyStanding.UNKNOWN,
    }
    assert world.keyring.secrets == {}


def test_a_mainnet_key_that_can_withdraw_is_refused_and_stored_nowhere(
    world: World,
) -> None:
    _everything_unknown(world)
    world.mainnet.keys.known = {KEY}
    world.mainnet.api_restrictions.enable_spot_and_margin_trading = True
    world.mainnet.api_restrictions.enable_withdrawals = True

    result = world.enrol()

    assert result.refusal is EnrolmentRefusal.WITHDRAWAL_ENABLED
    assert result.stored == ()
    assert world.keyring.secrets == {}
    _nothing_was_placed(world)


def test_a_spot_only_mainnet_key_is_stored_for_spot_mainnet_alone(world: World) -> None:
    _everything_unknown(world)
    world.mainnet.keys.known = {KEY}
    world.mainnet.api_restrictions.enable_spot_and_margin_trading = True

    result = world.enrol()

    assert result.refusal is None
    assert result.stored == (SPOT_MAINNET,)
    assert world.key_of(SPOT_MAINNET) == KEY
    assert world.key_of(FUTURES_MAINNET) is None
    assert set(world.keyring.secrets) == {
        "spot_mainnet_api_key",
        "spot_mainnet_api_secret",
    }
    assert not world.secrets_file.exists()
    _nothing_was_placed(world)


def test_a_mainnet_key_that_may_trade_both_markets_is_stored_for_both(
    world: World,
) -> None:
    _everything_unknown(world)
    world.mainnet.keys.known = {KEY}
    world.mainnet.api_restrictions.enable_spot_and_margin_trading = True
    world.mainnet.api_restrictions.enable_futures = True

    result = world.enrol()

    assert result.stored == (SPOT_MAINNET, FUTURES_MAINNET)
    assert world.key_of(SPOT_MAINNET) == world.key_of(FUTURES_MAINNET) == KEY


def test_a_read_only_mainnet_key_is_refused_because_it_may_trade_nowhere(
    world: World,
) -> None:
    _everything_unknown(world)
    world.mainnet.keys.known = {KEY}

    result = world.enrol()

    assert result.refusal is EnrolmentRefusal.NO_TRADING_PERMISSION
    assert world.keyring.secrets == {}


def test_a_spot_testnet_key_is_stored_for_spot_testnet_and_the_futures_testnet_key_stays(
    world: World,
) -> None:
    """The owner's case, the other way round: adding one venue's key reads every
    other venue's back unchanged."""
    _everything_unknown(world)
    world.futures_testnet.keys.known = {OLD_FUTURES_TESTNET_KEY}
    world.providers[FUTURES_TESTNET].save_to_file(OLD_FUTURES_TESTNET_KEY, SECRET)
    world.spot_testnet.keys.known = {KEY}

    result = world.enrol()

    assert result.stored == (SPOT_TESTNET,)
    assert world.key_of(SPOT_TESTNET) == KEY
    assert world.key_of(FUTURES_TESTNET) == OLD_FUTURES_TESTNET_KEY
    assert world.keyring.secrets == {}
    # Mainnet was asked first and did not know it; the Futures Testnet was never asked.
    assert _standing(result) == {
        KeyEnvironment.MAINNET: KeyStanding.UNKNOWN,
        KeyEnvironment.SPOT_TESTNET: KeyStanding.ACCEPTED,
    }


def test_a_futures_testnet_key_is_stored_for_futures_testnet_alone(
    world: World,
) -> None:
    _everything_unknown(world)
    world.futures_testnet.keys.known = {KEY}

    result = world.enrol()

    assert result.stored == (FUTURES_TESTNET,)
    assert world.key_of(FUTURES_TESTNET) == KEY
    assert world.key_of(SPOT_TESTNET) is None


def test_a_mainnet_key_pasted_while_a_testnet_key_exists_keeps_the_testnet_key(
    world: World,
) -> None:
    """`BUG-176` end to end: the owner's mainnet key lands in the keyring under the
    mainnet venue's names and the working testnet key is untouched."""
    _everything_unknown(world)
    world.providers[FUTURES_TESTNET].save_to_file(OLD_FUTURES_TESTNET_KEY, SECRET)
    world.mainnet.keys.known = {KEY}
    world.mainnet.api_restrictions.enable_futures = True

    result = world.enrol()

    assert result.stored == (FUTURES_MAINNET,)
    assert world.key_of(FUTURES_TESTNET) == OLD_FUTURES_TESTNET_KEY
    assert world.key_of(FUTURES_MAINNET) == KEY


def test_replacing_one_venues_key_leaves_the_other_mainnet_venue_alone(
    world: World,
) -> None:
    _everything_unknown(world)
    world.providers[FUTURES_MAINNET].save_to_file(OLD_SPOT_MAINNET_KEY, SECRET)
    world.mainnet.keys.known = {KEY}
    world.mainnet.api_restrictions.enable_spot_and_margin_trading = True
    world.mainnet.api_restrictions.enable_futures = True

    result = world.enrol(only_for=SPOT_MAINNET)

    assert result.stored == (SPOT_MAINNET,)
    assert world.key_of(SPOT_MAINNET) == KEY
    assert world.key_of(FUTURES_MAINNET) == OLD_SPOT_MAINNET_KEY


def test_a_key_replacing_another_venues_key_is_refused_and_says_which_venue_it_is_for(
    world: World,
) -> None:
    _everything_unknown(world)
    world.spot_testnet.keys.known = {KEY}

    result = world.enrol(only_for=FUTURES_TESTNET)

    assert result.refusal is EnrolmentRefusal.OTHER_VENUE
    assert result.venues == (SPOT_TESTNET,)
    assert world.key_of(SPOT_TESTNET) is None
    assert world.key_of(FUTURES_TESTNET) is None


def test_a_venue_whose_key_is_an_environment_variable_is_not_written(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _everything_unknown(world)
    world.spot_testnet.keys.known = {KEY}
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_API_KEY", "from-env")
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_API_SECRET", "from-env")

    result = world.enrol()

    assert result.refusal is EnrolmentRefusal.FROM_ENVIRONMENT
    assert result.venues == (SPOT_TESTNET,)
    assert not world.secrets_file.exists()
    assert world.providers[SPOT_TESTNET].resolve().source is CredentialsSource.ENV


def test_a_locked_keyring_refuses_a_mainnet_key_and_says_so(tmp_path: Path) -> None:
    for world in build_world(tmp_path, UnavailableSecretStore()):  # type: ignore[arg-type]
        _everything_unknown(world)
        world.mainnet.keys.known = {KEY}
        world.mainnet.api_restrictions.enable_spot_and_margin_trading = True

        result = world.enrol()

        assert result.refusal is EnrolmentRefusal.KEYRING_UNAVAILABLE
        assert result.stored == ()


def test_an_exchange_under_maintenance_is_not_mistaken_for_an_unknown_key(
    world: World,
) -> None:
    _everything_unknown(world)
    world.mainnet.maintenance.on = True

    result = world.enrol()

    by_environment = {v.environment: v for v in result.verdicts}
    mainnet = by_environment[KeyEnvironment.MAINNET]
    assert mainnet.standing is KeyStanding.UNREACHABLE
    assert mainnet.failure is ConnectionFailureKind.MAINTENANCE
    assert by_environment[KeyEnvironment.SPOT_TESTNET].standing is KeyStanding.UNKNOWN


def test_an_empty_secret_asks_the_exchange_nothing(world: World) -> None:
    handler = EnrolKeyCommandHandler(
        BinanceKeyEnvironmentProbe(), FakeVenueContexts(*world._contexts())
    )

    result = handler.execute(EnrolKeyCommand(ExchangeCredentials(KEY, "  ")))

    assert result.refusal is EnrolmentRefusal.INCOMPLETE
    assert all(server.requests == [] for server in world.servers())
