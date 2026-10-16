"""`EPIC-036D1` — Tools → Options → Alerts: the page, the status line, Save and Remove.

What the owner sees and is told, over the real use cases (`alerts_page_world`): the page
is an Options page, and a webhook is saved only when it is a Discord webhook URL.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QLineEdit
from Sagittarius_Elite_Warrior.src.core.contracts.i_options_section import (
    IOptionsSection,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_webhook_channel import (
    DISCORD_WEBHOOK_SECRET,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import (
    InMemorySecretStore,
    UnavailableSecretStore,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.ui.options.alerts_page_world import (
    CHANNEL,
    REMOVE,
    SAVE,
    SAVED,
    SEND_TEST,
    STATUS,
    URL,
    AlertsPage,
    assert_no_secret,
    build_page,
    stored_page,
)


@pytest.fixture
def page(qapp, request, monkeypatch) -> AlertsPage:
    return build_page(request, monkeypatch)


# -- the page is an Options page --------------------------------------------


def test_the_page_satisfies_ioptionssection_and_is_titled_alerts(page) -> None:
    assert isinstance(page.presenter, IOptionsSection)
    assert page.presenter.title == "Alerts"
    assert page.presenter.widget() is page.view


def test_the_page_is_never_dirty_because_every_change_is_saved_by_its_own_button(
    page,
) -> None:
    page.type_in_field(URL)

    assert page.presenter.is_dirty() is False
    assert page.presenter.validation_message() is None


# -- the webhook field is masked --------------------------------------------


def test_the_webhook_field_is_a_masked_password_field(page) -> None:
    field = page.view.findChild(QLineEdit, "txtDiscordWebhook")

    assert field.echoMode() is QLineEdit.EchoMode.Password


# -- the channel status line -------------------------------------------------


def test_with_no_webhook_and_no_lane_the_status_says_off(page) -> None:
    assert "off" in page.label(CHANNEL).lower()
    assert "no discord webhook is saved" in page.label(CHANNEL).lower()
    assert not page.button(REMOVE).isEnabled()
    assert not page.button(SEND_TEST).isEnabled()


def test_a_stored_webhook_with_a_running_lane_says_on_and_shows_only_a_hint(
    request, monkeypatch, qapp
) -> None:
    page = stored_page(request, monkeypatch, running=True)

    assert page.label(CHANNEL).startswith("On")
    assert "w9Kp" in page.label(SAVED)
    assert_no_secret(page.everything_on_screen(), "the page")
    assert page.button(REMOVE).isEnabled()
    assert page.button(SEND_TEST).isEnabled()


def test_a_stored_webhook_with_no_lane_tells_the_owner_to_restart(
    request, monkeypatch, qapp
) -> None:
    page = stored_page(request, monkeypatch, running=False)

    assert "restart the app to start sending" in page.label(CHANNEL).lower()


def test_a_removed_webhook_with_a_running_lane_says_restart_to_stop(
    request, monkeypatch, qapp
) -> None:
    page = build_page(request, monkeypatch, running=True)

    assert "restart" in page.label(CHANNEL).lower()
    assert "refused" in page.label(CHANNEL).lower()


# -- Save ---------------------------------------------------------------------


def test_save_stores_the_webhook_clears_the_field_and_says_what_to_do_next(
    page,
) -> None:
    page.type_in_field(URL)

    page.click(SAVE)

    assert page.store.read(DISCORD_WEBHOOK_SECRET) == URL
    assert page.field_text == "", "the URL is not kept in the field once saved"
    assert "w9Kp" in page.label(SAVED)
    assert "restart the app to start sending" in page.label(CHANNEL).lower()
    assert page.button(REMOVE).isEnabled()
    assert_no_secret(page.everything_on_screen(), "the page after a save")


def test_save_on_a_running_lane_takes_effect_for_the_next_send_without_a_restart(
    request, monkeypatch, qapp
) -> None:
    page = stored_page(request, monkeypatch, running=True)
    page.type_in_field(URL.replace("w9Kp", "NEW1"))

    page.click(SAVE)

    assert page.label(CHANNEL).startswith("On")
    assert "NEW1" in page.label(SAVED)
    assert "restart" not in page.label(CHANNEL).lower()


@pytest.mark.parametrize(
    ("typed", "words"),
    [
        ("", "paste"),
        ("hello", "not a discord webhook url"),
        (URL.replace("https", "http"), "not a discord webhook url"),
        (URL.replace("discord.com", "example.com"), "not a discord webhook url"),
    ],
)
def test_an_invalid_value_is_not_saved_and_the_page_says_why(
    page, typed: str, words: str
) -> None:
    page.type_in_field(typed)
    page.view.findChild(QLineEdit, "txtDiscordWebhook").setFocus()

    page.click(SAVE)

    assert page.store.read(DISCORD_WEBHOOK_SECRET) is None, "an invalid URL was saved"
    assert words in page.label(STATUS).lower()
    assert page.label(STATUS).startswith("Error:")
    assert_no_secret(page.labels_only(), "a label after a refusal")


def test_an_invalid_value_leaves_the_webhook_already_saved(
    request, monkeypatch, qapp
) -> None:
    page = stored_page(request, monkeypatch, running=True)
    page.type_in_field("hello")

    page.click(SAVE)

    assert page.store.read(DISCORD_WEBHOOK_SECRET) == URL


def test_a_save_the_store_refuses_says_so_and_stores_nothing(
    request, monkeypatch, qapp
) -> None:
    page = build_page(request, monkeypatch, store=UnavailableSecretStore())
    page.type_in_field(URL)

    page.click(SAVE)

    assert "keyring" in page.label(STATUS).lower()
    assert "nothing was saved" in page.label(STATUS).lower()
    assert_no_secret(page.labels_only(), "a label after a refused save")


def test_a_webhook_another_store_overrides_is_not_reported_as_saved(
    request, monkeypatch, qapp
) -> None:
    from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
        CredentialsSource,
    )
    from Sagittarius_Elite_Warrior.src.support.secrets.ordered_secret_stores import (
        OrderedSecretStores,
        SecretBackend,
    )

    stores = OrderedSecretStores(
        [
            SecretBackend(
                CredentialsSource.SYSTEMD_CREDENTIAL,
                InMemorySecretStore(
                    **{
                        DISCORD_WEBHOOK_SECRET: "https://discord.com/api/webhooks/7/prov_AAAA"
                    }
                ),
            ),
            SecretBackend(
                CredentialsSource.KEYRING, InMemorySecretStore(), writable=True
            ),
        ]
    )
    page = build_page(request, monkeypatch, store=stores)
    page.type_in_field(URL)

    page.click(SAVE)

    assert "systemd credential or secret file" in page.label(STATUS).lower()
    assert "not used" in page.label(STATUS).lower()


# -- Remove -------------------------------------------------------------------


def test_remove_asks_with_its_own_verbs_and_keeping_is_the_default(
    request, monkeypatch, qapp
) -> None:
    page = stored_page(request, monkeypatch, running=True)
    page.answers.append(False)

    page.click(REMOVE)

    [question] = page.asked
    assert question.act == "Remove webhook"
    assert question.keep == "Keep webhook"
    assert question.title == "Remove Discord Webhook"
    assert page.store.read(DISCORD_WEBHOOK_SECRET) == URL, "keeping must keep"


def test_confirmed_remove_forgets_the_webhook_and_says_when_it_stops(
    request, monkeypatch, qapp
) -> None:
    page = stored_page(request, monkeypatch, running=True)
    page.answers.append(True)

    page.click(REMOVE)

    assert page.store.read(DISCORD_WEBHOOK_SECRET) is None
    assert "restart" in page.label(CHANNEL).lower()
    assert page.label(SAVED) == "No webhook saved."
    assert not page.button(REMOVE).isEnabled()
    assert_no_secret(page.everything_on_screen(), "the page after a removal")


def test_remove_that_leaves_an_overriding_webhook_is_not_reported_as_removed(
    request, monkeypatch, qapp
) -> None:
    from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
        CredentialsSource,
    )
    from Sagittarius_Elite_Warrior.src.support.secrets.ordered_secret_stores import (
        OrderedSecretStores,
        SecretBackend,
    )

    stores = OrderedSecretStores(
        [
            SecretBackend(
                CredentialsSource.SYSTEMD_CREDENTIAL,
                InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: URL}),
            ),
            SecretBackend(
                CredentialsSource.KEYRING, InMemorySecretStore(), writable=True
            ),
        ]
    )
    page = build_page(request, monkeypatch, store=stores, running=True)
    page.answers.append(True)

    page.click(REMOVE)

    assert "still set" in page.label(STATUS).lower()
