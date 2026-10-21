"""`EPIC-036D4` — saving, removing and describing the Telegram bot token and chat id the
Options page manages. The token is the secret: these tests go red if an invalid pair is stored,
or if the token reaches an outcome, a state, a log record or an exception."""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.registered_channel_catalog import (
    RegisteredChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.telegram_channel import (
    TELEGRAM_CHANNEL_ID,
    TELEGRAM_CHAT_SECRET,
    TELEGRAM_TOKEN_SECRET,
    is_bot_token,
    is_chat_id,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.telegram_credentials_setup import (
    TelegramChannelSpec,
    TelegramCredentialsSetup,
    TelegramRemoval,
    TelegramSave,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_channel import (
    FakeAlertChannel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.src.support.secrets.ordered_secret_stores import (
    OrderedSecretStores,
    SecretBackend,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import (
    InMemorySecretStore,
    UnavailableSecretStore,
)

BOT_KEY = "123456789:AAH-top_secret_TOKEN_abcdefghijklmnopqrst"
OTHER_BOT_KEY = "987654321:AAH-another_secret_TOKEN_zyxwvutsrqponm"
CHAT = "5550123"
SPEC = TelegramChannelSpec(
    TELEGRAM_CHANNEL_ID,
    TELEGRAM_TOKEN_SECRET,
    TELEGRAM_CHAT_SECRET,
    is_bot_token,
    is_chat_id,
)


def setup_over(store, *, running: bool = False) -> TelegramCredentialsSetup:  # type: ignore[no-untyped-def]
    channels = {TELEGRAM_CHANNEL_ID: FakeAlertChannel()} if running else {}
    return TelegramCredentialsSetup(store, SPEC, RegisteredChannelCatalog(channels))


def test_a_valid_pair_is_saved_under_the_channels_secret_names() -> None:
    store = InMemorySecretStore()

    outcome = setup_over(store).save(BOT_KEY, CHAT)

    assert outcome is TelegramSave.SAVED
    assert store.secrets == {
        TELEGRAM_TOKEN_SECRET: BOT_KEY,
        TELEGRAM_CHAT_SECRET: CHAT,
    }


def test_the_values_are_trimmed() -> None:
    store = InMemorySecretStore()

    outcome = setup_over(store).save(f"  {BOT_KEY}\n", f" {CHAT} ")

    assert outcome is TelegramSave.SAVED
    assert store.secrets[TELEGRAM_TOKEN_SECRET] == BOT_KEY


@pytest.mark.parametrize(
    ("token", "chat", "expected"),
    [
        ("", CHAT, TelegramSave.EMPTY_TOKEN),
        (BOT_KEY, "  ", TelegramSave.EMPTY_CHAT),
        ("not-a-token", CHAT, TelegramSave.NOT_A_BOT_TOKEN),
        (BOT_KEY, "not a chat", TelegramSave.NOT_A_CHAT_ID),
    ],
    ids=["no-token", "no-chat", "bad-token", "bad-chat"],
)
def test_an_invalid_value_stores_nothing_and_keeps_an_earlier_pair(
    token: str, chat: str, expected: TelegramSave
) -> None:
    store = InMemorySecretStore(
        **{TELEGRAM_TOKEN_SECRET: OTHER_BOT_KEY, TELEGRAM_CHAT_SECRET: "77"}
    )

    outcome = setup_over(store).save(token, chat)

    assert outcome is expected
    assert store.secrets == {
        TELEGRAM_TOKEN_SECRET: OTHER_BOT_KEY,
        TELEGRAM_CHAT_SECRET: "77",
    }


def test_saving_over_a_stored_pair_replaces_it_which_is_the_rotation() -> None:
    store = InMemorySecretStore(
        **{TELEGRAM_TOKEN_SECRET: OTHER_BOT_KEY, TELEGRAM_CHAT_SECRET: "77"}
    )

    outcome = setup_over(store).save(BOT_KEY, CHAT)

    assert outcome is TelegramSave.SAVED
    assert store.secrets[TELEGRAM_TOKEN_SECRET] == BOT_KEY


def test_a_machine_with_no_usable_store_says_so_and_stores_nothing() -> None:
    assert (
        setup_over(UnavailableSecretStore()).save(BOT_KEY, CHAT)
        is TelegramSave.STORE_UNAVAILABLE
    )


def test_a_value_another_store_overrides_is_reported_not_called_saved() -> None:
    provisioned = InMemorySecretStore(
        **{TELEGRAM_TOKEN_SECRET: OTHER_BOT_KEY, TELEGRAM_CHAT_SECRET: "77"}
    )
    keyring = InMemorySecretStore()
    stores = OrderedSecretStores(
        [
            SecretBackend(CredentialsSource.SYSTEMD_CREDENTIAL, provisioned),
            SecretBackend(CredentialsSource.KEYRING, keyring, writable=True),
        ]
    )

    outcome = setup_over(stores).save(BOT_KEY, CHAT)

    assert outcome is TelegramSave.OVERRIDDEN
    assert keyring.secrets == {
        TELEGRAM_TOKEN_SECRET: BOT_KEY,
        TELEGRAM_CHAT_SECRET: CHAT,
    }


def test_the_state_of_a_saved_pair_shows_the_chat_and_four_characters_of_the_token() -> (
    None
):
    store = InMemorySecretStore(
        **{TELEGRAM_TOKEN_SECRET: BOT_KEY, TELEGRAM_CHAT_SECRET: CHAT}
    )

    state = setup_over(store, running=True).state()

    assert state.usable and state.running
    assert state.hint == BOT_KEY[-4:]
    assert state.chat == CHAT
    assert BOT_KEY not in repr(state)


def test_a_half_saved_pair_is_stored_but_not_usable() -> None:
    store = InMemorySecretStore(**{TELEGRAM_TOKEN_SECRET: BOT_KEY})

    state = setup_over(store).state()

    assert state.stored and not state.usable
    assert state.hint == ""


def test_an_empty_store_has_nothing() -> None:
    state = setup_over(InMemorySecretStore()).state()

    assert not state.stored and not state.usable and not state.running


def test_remove_forgets_both_values() -> None:
    store = InMemorySecretStore(
        **{TELEGRAM_TOKEN_SECRET: BOT_KEY, TELEGRAM_CHAT_SECRET: CHAT}
    )

    outcome = setup_over(store).remove()

    assert outcome is TelegramRemoval.REMOVED
    assert store.secrets == {}


def test_remove_with_nothing_stored_says_so() -> None:
    assert setup_over(InMemorySecretStore()).remove() is TelegramRemoval.NOTHING_STORED


def test_remove_that_the_store_refuses_is_reported_and_leaves_the_pair() -> None:
    class CannotDelete(InMemorySecretStore):
        def delete(self, name: str) -> None:
            raise SecretStoreUnavailableError(f"cannot forget {self.secrets[name]}")

    store = CannotDelete(**{TELEGRAM_TOKEN_SECRET: BOT_KEY, TELEGRAM_CHAT_SECRET: CHAT})

    outcome = setup_over(store).remove()

    assert outcome is TelegramRemoval.STORE_UNAVAILABLE
    assert TELEGRAM_TOKEN_SECRET in store.secrets


def test_remove_that_leaves_an_overriding_pair_says_it_is_still_set() -> None:
    provisioned = InMemorySecretStore(
        **{TELEGRAM_TOKEN_SECRET: OTHER_BOT_KEY, TELEGRAM_CHAT_SECRET: "77"}
    )
    keyring = InMemorySecretStore(
        **{TELEGRAM_TOKEN_SECRET: BOT_KEY, TELEGRAM_CHAT_SECRET: CHAT}
    )
    stores = OrderedSecretStores(
        [
            SecretBackend(CredentialsSource.SYSTEMD_CREDENTIAL, provisioned),
            SecretBackend(CredentialsSource.KEYRING, keyring, writable=True),
        ]
    )

    outcome = setup_over(stores).remove()

    assert outcome is TelegramRemoval.STILL_SET_ELSEWHERE


def test_no_outcome_state_or_log_line_holds_the_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemorySecretStore()
    setup = setup_over(store)

    with caplog.at_level(logging.DEBUG):
        saved = setup.save(BOT_KEY, CHAT)
        state = setup.state()
        setup.save("not-a-token", CHAT)
        setup.remove()

    for text in (repr(saved), repr(state), caplog.text):
        assert BOT_KEY not in text
        assert BOT_KEY.split(":")[1] not in text


class _SecondWriteRefused(InMemorySecretStore):
    """A store whose chat write fails after the token write went through."""

    def write(self, name: str, value: str) -> None:
        if name == TELEGRAM_CHAT_SECRET:
            raise SecretStoreUnavailableError("refused")
        super().write(name, value)


class _SecondDeleteRefused(InMemorySecretStore):
    def delete(self, name: str) -> None:
        if name == TELEGRAM_CHAT_SECRET:
            raise SecretStoreUnavailableError("refused")
        super().delete(name)


def test_a_refused_chat_write_puts_the_earlier_token_back() -> None:
    store = _SecondWriteRefused(
        **{TELEGRAM_TOKEN_SECRET: OTHER_BOT_KEY, TELEGRAM_CHAT_SECRET: CHAT}
    )

    outcome = setup_over(store).save(BOT_KEY, "99")

    assert outcome is TelegramSave.STORE_UNAVAILABLE
    assert store.secrets == {
        TELEGRAM_TOKEN_SECRET: OTHER_BOT_KEY,
        TELEGRAM_CHAT_SECRET: CHAT,
    }


def test_a_refused_chat_write_leaves_no_token_when_there_was_none() -> None:
    store = _SecondWriteRefused()

    setup_over(store).save(BOT_KEY, "99")

    assert store.secrets == {}


def test_a_refused_chat_delete_puts_the_token_back() -> None:
    store = _SecondDeleteRefused(
        **{TELEGRAM_TOKEN_SECRET: OTHER_BOT_KEY, TELEGRAM_CHAT_SECRET: CHAT}
    )

    outcome = setup_over(store).remove()

    assert outcome is TelegramRemoval.STORE_UNAVAILABLE
    assert store.secrets == {
        TELEGRAM_TOKEN_SECRET: OTHER_BOT_KEY,
        TELEGRAM_CHAT_SECRET: CHAT,
    }
