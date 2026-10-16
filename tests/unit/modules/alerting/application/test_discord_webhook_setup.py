"""`EPIC-036D1` — saving, removing and describing the Discord webhook the Options
page manages: the secret write path, with the URL kept out of everything it returns.

The URL of a webhook *is* its secret (N3). These tests go red if an invalid value
is stored, or if the URL reaches an outcome, a state, a log record or an exception.
"""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    ISecretStore,
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_message import (
    is_discord_webhook_url,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_webhook_channel import (
    DISCORD_CHANNEL_ID,
    DISCORD_WEBHOOK_SECRET,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.registered_channel_catalog import (
    RegisteredChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.discord_webhook_setup import (
    DiscordWebhookSetup,
    WebhookChannelSpec,
    WebhookRemoval,
    WebhookSave,
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

URL = "https://discord.com/api/webhooks/1234567890/Zq-top_secret_TOKEN-w9Kp"
OTHER_URL = "https://discord.com/api/webhooks/99/another_Secret_token_AbCd"
SPEC = WebhookChannelSpec(
    DISCORD_CHANNEL_ID, DISCORD_WEBHOOK_SECRET, is_discord_webhook_url
)


def setup_over(store: ISecretStore, *, running: bool = False) -> DiscordWebhookSetup:
    channels = {DISCORD_CHANNEL_ID: FakeAlertChannel()} if running else {}
    return DiscordWebhookSetup(store, SPEC, RegisteredChannelCatalog(channels))


def test_a_discord_webhook_url_is_saved_under_the_channels_secret_name() -> None:
    store = InMemorySecretStore()

    outcome = setup_over(store).save(f"  {URL}\n")

    assert outcome is WebhookSave.SAVED
    assert store.secrets == {DISCORD_WEBHOOK_SECRET: URL}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", WebhookSave.EMPTY),
        ("   \n", WebhookSave.EMPTY),
        ("not a url", WebhookSave.NOT_A_DISCORD_WEBHOOK),
        ("http://discord.com/api/webhooks/1/abc", WebhookSave.NOT_A_DISCORD_WEBHOOK),
        ("https://example.com/api/webhooks/1/abc", WebhookSave.NOT_A_DISCORD_WEBHOOK),
        (
            "https://discord.com.evil.example/api/webhooks/1/abc",
            WebhookSave.NOT_A_DISCORD_WEBHOOK,
        ),
        ("https://discord.com/api/webhooks/1", WebhookSave.NOT_A_DISCORD_WEBHOOK),
        (f"{URL}/extra", WebhookSave.NOT_A_DISCORD_WEBHOOK),
        (f"{URL} {OTHER_URL}", WebhookSave.NOT_A_DISCORD_WEBHOOK),
    ],
)
def test_a_value_that_is_not_a_discord_webhook_url_is_never_saved(
    value: str, expected: WebhookSave
) -> None:
    store = InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: OTHER_URL})

    outcome = setup_over(store).save(value)

    assert outcome is expected
    assert store.secrets == {DISCORD_WEBHOOK_SECRET: OTHER_URL}, (
        "a refused value must leave the earlier webhook as it was"
    )


def test_a_machine_with_no_usable_store_refuses_the_save_in_words_without_the_url() -> (
    None
):
    outcome = setup_over(UnavailableSecretStore()).save(URL)

    assert outcome is WebhookSave.STORE_UNAVAILABLE


def test_a_store_that_quotes_the_url_in_its_error_does_not_pass_it_on() -> None:
    class QuotingStore(InMemorySecretStore):
        def write(self, name: str, value: str) -> None:
            raise SecretStoreUnavailableError(f"cannot store {value}")

    outcome = setup_over(QuotingStore()).save(URL)

    assert outcome is WebhookSave.STORE_UNAVAILABLE
    assert URL not in repr(outcome)


def test_a_webhook_that_another_store_overrides_is_reported_as_not_in_use() -> None:
    """On a host that provisions the webhook (a systemd credential), the keyring entry
    the page writes is never read: saying "saved" would be a lie."""
    provisioned = InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: OTHER_URL})
    keyring = InMemorySecretStore()
    stores = OrderedSecretStores(
        [
            SecretBackend(CredentialsSource.SYSTEMD_CREDENTIAL, provisioned),
            SecretBackend(CredentialsSource.KEYRING, keyring, writable=True),
        ]
    )

    outcome = setup_over(stores).save(URL)

    assert outcome is WebhookSave.OVERRIDDEN
    assert keyring.secrets == {DISCORD_WEBHOOK_SECRET: URL}


def test_remove_forgets_the_webhook() -> None:
    store = InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: URL})

    outcome = setup_over(store).remove()

    assert outcome is WebhookRemoval.REMOVED
    assert store.secrets == {}


def test_remove_with_nothing_stored_says_so() -> None:
    assert setup_over(InMemorySecretStore()).remove() is WebhookRemoval.NOTHING_STORED


def test_remove_on_a_machine_with_no_readable_store_has_nothing_to_remove() -> None:
    assert (
        setup_over(UnavailableSecretStore()).remove() is WebhookRemoval.NOTHING_STORED
    )


def test_remove_that_the_store_refuses_is_reported_and_leaves_the_webhook() -> None:
    class CannotDelete(InMemorySecretStore):
        def delete(self, name: str) -> None:
            raise SecretStoreUnavailableError(f"cannot forget {self.secrets[name]}")

    store = CannotDelete(**{DISCORD_WEBHOOK_SECRET: URL})

    outcome = setup_over(store).remove()

    assert outcome is WebhookRemoval.STORE_UNAVAILABLE
    assert store.secrets == {DISCORD_WEBHOOK_SECRET: URL}


def test_remove_that_leaves_an_overriding_webhook_says_it_is_still_set() -> None:
    provisioned = InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: URL})
    keyring = InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: OTHER_URL})
    stores = OrderedSecretStores(
        [
            SecretBackend(CredentialsSource.SYSTEMD_CREDENTIAL, provisioned),
            SecretBackend(CredentialsSource.KEYRING, keyring, writable=True),
        ]
    )

    outcome = setup_over(stores).remove()

    assert outcome is WebhookRemoval.STILL_SET_ELSEWHERE
    assert keyring.secrets == {}


def test_state_tells_stored_usable_and_running_without_the_url() -> None:
    store = InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: URL})

    state = setup_over(store, running=True).state()

    assert (state.stored, state.usable, state.running) == (True, True, True)
    assert state.hint == "w9Kp"
    assert URL not in repr(state)
    assert "top_secret" not in repr(state)


def test_state_with_nothing_stored_has_no_hint() -> None:
    state = setup_over(InMemorySecretStore()).state()

    assert (state.stored, state.usable, state.running, state.hint) == (
        False,
        False,
        False,
        "",
    )


def test_a_stored_value_that_is_not_a_webhook_url_is_stored_but_not_usable() -> None:
    state = setup_over(
        InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: "hand-edited-garbage"})
    ).state()

    assert (state.stored, state.usable, state.hint) == (True, False, "")


def test_state_follows_the_store_at_each_call_not_a_copy_made_at_boot() -> None:
    store = InMemorySecretStore()
    setup = setup_over(store)
    assert setup.state().stored is False

    setup.save(URL)

    assert setup.state().stored is True


@pytest.mark.parametrize("action", ["save", "invalid", "unavailable", "remove"])
def test_no_log_record_carries_the_url_on_any_path(
    action: str, caplog: pytest.LogCaptureFixture
) -> None:
    store: ISecretStore = (
        UnavailableSecretStore()
        if action == "unavailable"
        else InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: URL})
    )
    setup = setup_over(store)

    with caplog.at_level(logging.DEBUG):
        if action == "remove":
            setup.remove()
        elif action == "invalid":
            setup.save(URL.replace("https", "http"))
        else:
            setup.save(URL)
        setup.state()

    assert caplog.records, "the paths log what they decided"
    for record in caplog.records:
        rendered = record.getMessage() + str(record.exc_text) + repr(record.args)
        assert "top_secret" not in rendered
        assert "1234567890" not in rendered


def test_a_write_that_cannot_be_read_back_is_not_blamed_on_another_store() -> None:
    """A keyring that writes but reads as nothing is unusable, not shadowed."""

    class WriteOnly(InMemorySecretStore):
        def read(self, name: str) -> str | None:
            return None

    assert setup_over(WriteOnly()).save(URL) is WebhookSave.STORE_UNAVAILABLE
