"""`BUG-176` — enrolling, removing and listing keys, without a window or an exchange."""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.credentials.enrol_key import (
    EnrolKeyCommand,
    EnrolKeyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.credentials.remove_key import (
    RemoveKeyCommand,
    RemoveKeyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.list_venue_keys import (
    ListVenueKeysQuery,
    ListVenueKeysQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_enrolment import (
    EnrolmentRefusal,
    KeyRemoval,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
    KeyEnvironment,
    KeyStanding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_key import (
    key_fingerprint,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    EnvFirstCredentialsProvider,
    MainnetCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import (
    InMemorySecretStore,
    UnavailableSecretStore,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.ui.settings.key_page_world import (
    KEY,
    SECRET,
    VENUES,
    ScriptedKeyProbe,
    mainnet_accepts,
)

_SPOT_TESTNET = TradingVenue.SPOT_TESTNET
_FUTURES_TESTNET = TradingVenue.FUTURES_TESTNET
_SPOT_MAINNET = TradingVenue.SPOT_MAINNET


@pytest.fixture(autouse=True)
def _no_environment_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    for name in list(os.environ):
        if name.startswith("BINANCE_"):
            monkeypatch.delenv(name)


def _contexts(tmp_path: Path, keyring=None):
    file_source = SecretsFileSource(str(tmp_path / "secrets.local.json"))
    store = keyring if keyring is not None else InMemorySecretStore()
    providers = {
        v: (
            MainnetCredentialsProvider(store, v)
            if v.is_mainnet
            else EnvFirstCredentialsProvider(file_source, v)
        )
        for v in VENUES
    }
    return (
        FakeVenueContexts(
            *(fake_venue_context(v, credentials_provider=providers[v]) for v in VENUES)
        ),
        providers,
    )


def _enrol(probe, contexts, only_for=None, key=KEY, secret=SECRET):
    return EnrolKeyCommandHandler(probe, contexts).execute(
        EnrolKeyCommand(ExchangeCredentials(key, secret), only_for)
    )


def test_environments_are_asked_in_order_and_asking_stops_at_the_first_that_accepts(
    tmp_path,
) -> None:
    contexts, _ = _contexts(tmp_path)
    probe = ScriptedKeyProbe()
    probe.verdicts[KeyEnvironment.SPOT_TESTNET] = EnvironmentVerdict(
        KeyEnvironment.SPOT_TESTNET, KeyStanding.ACCEPTED
    )

    result = _enrol(probe, contexts)

    assert probe.asked == [KeyEnvironment.MAINNET, KeyEnvironment.SPOT_TESTNET]
    assert result.stored == (_SPOT_TESTNET,)


def test_a_key_nobody_accepts_asks_every_environment_and_stores_nothing(
    tmp_path,
) -> None:
    contexts, providers = _contexts(tmp_path)
    probe = ScriptedKeyProbe()

    result = _enrol(probe, contexts)

    assert probe.asked == list(KeyEnvironment)
    assert result.refusal is EnrolmentRefusal.NOT_ACCEPTED
    assert [p.resolve().source for p in providers.values()] == [
        CredentialsSource.NONE
    ] * 4


@pytest.mark.parametrize(("key", "secret"), [("", SECRET), (KEY, ""), ("  ", " ")])
def test_a_key_or_secret_left_empty_asks_the_exchange_nothing(
    tmp_path, key, secret
) -> None:
    contexts, _ = _contexts(tmp_path)
    probe = ScriptedKeyProbe()

    result = _enrol(probe, contexts, key=key, secret=secret)

    assert result.refusal is EnrolmentRefusal.INCOMPLETE
    assert probe.asked == []


def test_a_locked_keyring_stores_nothing_and_says_so(tmp_path) -> None:
    contexts, _ = _contexts(tmp_path, UnavailableSecretStore())  # type: ignore[arg-type]
    probe = ScriptedKeyProbe()
    probe.verdicts = mainnet_accepts(spot=True)

    result = _enrol(probe, contexts)

    assert result.refusal is EnrolmentRefusal.KEYRING_UNAVAILABLE
    assert result.stored == ()


def test_an_unwritable_secrets_file_stores_nothing_and_says_so(tmp_path) -> None:
    blocked = tmp_path / "secrets.local.json"
    blocked.mkdir()  # a directory where the file should be: opening it for writing fails
    contexts, _ = _contexts(tmp_path)
    probe = ScriptedKeyProbe()
    probe.verdicts[KeyEnvironment.SPOT_TESTNET] = EnvironmentVerdict(
        KeyEnvironment.SPOT_TESTNET, KeyStanding.ACCEPTED
    )

    result = _enrol(probe, contexts)

    assert result.refusal is EnrolmentRefusal.FILE_NOT_WRITABLE


def test_the_command_prints_the_key_masked_so_it_may_be_logged() -> None:
    command = EnrolKeyCommand(ExchangeCredentials(KEY, SECRET))

    assert SECRET not in repr(command)
    assert KEY not in repr(command)


def test_remove_forgets_a_stored_key_and_nothing_else(tmp_path) -> None:
    contexts, providers = _contexts(tmp_path)
    providers[_SPOT_MAINNET].save_to_file(KEY, SECRET)
    providers[_SPOT_TESTNET].save_to_file("t" * 20, "s")

    removal = RemoveKeyCommandHandler(contexts).execute(
        RemoveKeyCommand(venue=_SPOT_MAINNET)
    )

    assert removal is KeyRemoval.REMOVED
    assert providers[_SPOT_MAINNET].resolve().source is CredentialsSource.NONE
    assert providers[_SPOT_TESTNET].resolve().credentials is not None


def test_removing_where_nothing_is_stored_is_already_as_asked(tmp_path) -> None:
    contexts, _ = _contexts(tmp_path)

    assert (
        RemoveKeyCommandHandler(contexts).execute(RemoveKeyCommand(venue=_SPOT_MAINNET))
        is KeyRemoval.NOTHING_STORED
    )


class _KeyringThatLocksAfterReading(InMemorySecretStore):
    """A keyring that holds the pair but refuses to delete it."""

    def delete(self, name: str) -> None:
        raise SecretStoreUnavailableError("locked")


def test_a_locked_keyring_cannot_remove_a_key_and_says_so() -> None:
    keyring = _KeyringThatLocksAfterReading(
        spot_mainnet_api_key=KEY, spot_mainnet_api_secret=SECRET
    )
    contexts = FakeVenueContexts(
        fake_venue_context(
            _SPOT_MAINNET,
            credentials_provider=MainnetCredentialsProvider(keyring, _SPOT_MAINNET),
        )
    )

    removal = RemoveKeyCommandHandler(contexts).execute(
        RemoveKeyCommand(venue=_SPOT_MAINNET)
    )

    assert removal is KeyRemoval.KEYRING_UNAVAILABLE
    assert keyring.secrets["spot_mainnet_api_key"] == KEY


def test_the_list_holds_a_fingerprint_and_a_source_per_venue_and_never_the_secret(
    tmp_path,
) -> None:
    contexts, providers = _contexts(tmp_path)
    providers[_SPOT_MAINNET].save_to_file(KEY, SECRET)

    rows = ListVenueKeysQueryHandler(contexts).execute(ListVenueKeysQuery())

    assert [r.venue for r in rows] == list(VENUES)
    spot = next(r for r in rows if r.venue is _SPOT_MAINNET)
    assert spot.fingerprint == "A1b2…Z9y8"
    assert spot.source is CredentialsSource.KEYRING
    assert SECRET not in repr(rows)
    assert KEY not in repr(rows)
    others = [r for r in rows if r.venue is not _SPOT_MAINNET]
    assert all(
        r.fingerprint is None and r.source is CredentialsSource.NONE for r in others
    )


def test_the_fingerprint_is_four_and_four_and_a_short_key_is_masked_whole() -> None:
    assert key_fingerprint("abcd" + "x" * 40 + "wxyz") == "abcd…wxyz"
    assert key_fingerprint("short-key") == "••••"
    assert key_fingerprint("") == "••••"
