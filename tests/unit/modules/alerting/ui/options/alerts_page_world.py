"""`EPIC-036D1` — the Options Alerts page over the real use cases, with no network.

The page, `DiscordWebhookSetup`, `SendTestToConfiguredChannels`, the catalog builder
and the Discord channel are the real ones; the secret store is in memory and the
webhook transport is scripted. Only those two boundaries are doubles.
"""

from __future__ import annotations

import concurrent.futures
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import Mock

from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import ISecretStore
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_message import (
    is_discord_webhook_url,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_webhook_channel import (
    DISCORD_CHANNEL_ID,
    DISCORD_WEBHOOK_SECRET,
    DiscordWebhookChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.registered_channel_catalog import (
    RegisteredChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.telegram_channel import (
    TELEGRAM_CHANNEL_ID,
    TELEGRAM_CHAT_SECRET,
    TELEGRAM_TOKEN_SECRET,
    TelegramChannel,
    is_bot_token,
    is_chat_id,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.discord_webhook_setup import (
    DiscordWebhookSetup,
    WebhookChannelSpec,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.send_test_to_configured_channels import (
    SendTestToConfiguredChannels,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.telegram_credentials_setup import (
    TelegramChannelSpec,
    TelegramCredentialsSetup,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.composition.channel_bindings import (
    ChannelSecrets,
    DescriptorChannelCatalogBuilder,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_bot_alert_modes import (
    IBotAlertModes,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_settings_presenter import (
    AlertsSettingsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_settings_view import (
    AlertsSettingsView,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.sources.bot_source_world import (
    Bots,
)
from sagittarius_engine.interfaces.i_logger import ILogger
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

#: Every part of this URL that is secret has a marker the tests search for.
URL = "https://discord.com/api/webhooks/1234567890/Zq-top_secret_TOKEN-w9Kp"
#: Strings that, found anywhere a person or a log could see, mean the URL leaked.
SECRET_PARTS = ("top_secret", "1234567890", "Zq-top", "TOKEN-w9Kp")


class ForwardingLogger(ILogger):
    """The presenter's `ILogger`, forwarding to stdlib logging so a test reads every
    record the page makes (a `Mock` logger would make the "no URL in a log" tests vacuous)."""

    def __init__(self) -> None:
        self._logger = logging.getLogger("App.Alerting.Page")

    def _log(self, level: int, message: str) -> None:
        self._logger.log(level, "%s", message)

    def info(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.INFO, message)

    def warning(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.WARNING, message)

    def error(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.ERROR, message)

    def debug(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.DEBUG, message)

    def critical(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.CRITICAL, message)

    def trace(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.DEBUG, message)


class InlineThreads(IThreadManager):
    """Runs each task as it is submitted, or holds it for the test to release."""

    def __init__(self) -> None:
        self.held: list[Callable[[], None]] | None = None

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        if self.held is not None:
            self.held.append(lambda: future.set_result(task(*args, **kwargs)))
        else:
            future.set_result(task(*args, **kwargs))
        return future

    def shutdown(self, wait: bool = True) -> None:
        return None


class _Resolver:
    def __init__(self, store: ISecretStore, transport: IWebhookTransport) -> None:
        self._ports: dict[type, object] = {
            ChannelSecrets: ChannelSecrets(store),
            IWebhookTransport: transport,
            IAlertClock: FakeAlertClock(),
        }

    def resolve[T](self, abstract: type[T]) -> T:
        return self._ports[abstract]  # type: ignore[return-value]


@dataclass
class AlertsPage:
    presenter: AlertsSettingsPresenter
    view: AlertsSettingsView
    store: ISecretStore
    transport: FakeWebhookTransport
    notifier: RecordingNotifier
    threads: InlineThreads
    modes: JsonAlertSettings
    asked: list[Any] = field(default_factory=list)
    answers: list[bool] = field(default_factory=list)

    def type_in_field(self, text: str) -> None:
        self.view.findChild(QLineEdit, "txtDiscordWebhook").setText(text)

    def click(self, object_name: str) -> None:
        button = self.view.findChild(QPushButton, object_name)
        assert button is not None, object_name
        assert button.isEnabled(), f"{object_name} is disabled"
        button.click()

    def button(self, object_name: str) -> QPushButton:
        return self.view.findChild(QPushButton, object_name)

    @property
    def field_text(self) -> str:
        return self.view.findChild(QLineEdit, "txtDiscordWebhook").text()

    def label(self, object_name: str) -> str:
        return self.view.findChild(QLabel, object_name).text()

    def everything_on_screen(self) -> str:
        """Every label's text and every line edit's text: what a person can read."""
        texts = [label.text() for label in self.view.findChildren(QLabel)]
        texts += [edit.text() for edit in self.view.findChildren(QLineEdit)]
        texts += [button.text() for button in self.view.findChildren(QPushButton)]
        return "\n".join(texts)

    def labels_only(self) -> str:
        return "\n".join(label.text() for label in self.view.findChildren(QLabel))

    def told_the_user(self) -> str:
        """Every headline and detail the notifier was given."""
        return "\n".join(f"{n.headline}\n{n.detail}" for n in self.notifier.failures)


def build_page(
    request: Any,
    monkeypatch: Any,
    *,
    store: ISecretStore | None = None,
    running: bool = False,
    telegram_running: bool = False,
    transport: FakeWebhookTransport | None = None,
    bots: Bots | None = None,
    modes: JsonAlertSettings | None = None,
) -> AlertsPage:
    store = store if store is not None else InMemorySecretStore()
    transport = transport if transport is not None else FakeWebhookTransport()
    resolver = _Resolver(store, transport)
    catalog = RegisteredChannelCatalog(
        {
            **(
                {DISCORD_CHANNEL_ID: DiscordWebhookChannel(store, transport)}
                if running
                else {}
            ),
            **(
                {TELEGRAM_CHANNEL_ID: TelegramChannel(store, transport)}
                if telegram_running
                else {}
            ),
        }
    )
    telegram_setup = TelegramCredentialsSetup(
        store,
        TelegramChannelSpec(
            TELEGRAM_CHANNEL_ID,
            TELEGRAM_TOKEN_SECRET,
            TELEGRAM_CHAT_SECRET,
            is_bot_token,
            is_chat_id,
            store.read,
        ),
        catalog,
    )
    setup = DiscordWebhookSetup(
        store,
        WebhookChannelSpec(
            DISCORD_CHANNEL_ID, DISCORD_WEBHOOK_SECRET, is_discord_webhook_url
        ),
        catalog,
    )
    sender = SendTestToConfiguredChannels(
        DescriptorChannelCatalogBuilder(resolver), FakeAlertClock()
    )
    notifier = RecordingNotifier()
    threads = InlineThreads()
    modes = modes or JsonAlertSettings(
        request.getfixturevalue("tmp_path") / "state" / "alert_settings.json"
    )
    services = {
        IBotAlertModes: modes,
        ICommandDispatcher: bots if bots is not None else Bots(),
        INotifier: notifier,
        ILogger: ForwardingLogger(),
        IThreadManager: threads,
        DiscordWebhookSetup: setup,
        TelegramCredentialsSetup: telegram_setup,
        SendTestToConfiguredChannels: sender,
    }
    container = Mock()
    container.resolve.side_effect = lambda interface: services.get(interface, Mock())

    view = AlertsSettingsView()
    request.addfinalizer(view.deleteLater)
    page = AlertsPage(
        presenter=AlertsSettingsPresenter(view, container),
        view=view,
        store=store,
        transport=transport,
        notifier=notifier,
        threads=threads,
        modes=modes,
    )

    def answer(_parent: Any, question: Any) -> bool:
        page.asked.append(question)
        return page.answers.pop(0) if page.answers else False

    monkeypatch.setattr(
        "Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_settings_view.ask_with_verbs",
        answer,
    )
    request.addfinalizer(presenter_shutdown(page.presenter))
    return page


def presenter_shutdown(presenter: AlertsSettingsPresenter) -> Callable[[], None]:
    return presenter.shutdown


SAVE = "btnSaveDiscordWebhook"
REMOVE = "btnRemoveDiscordWebhook"
SEND_TEST = "btnSendDiscordTest"
STATUS = "lblAlertsStatus"
CHANNEL = "lblDiscordChannelState"
SAVED = "lblDiscordSaved"


def stored_page(request: Any, monkeypatch: Any, *, running: bool) -> AlertsPage:
    """A page over a store that already holds the webhook."""
    return build_page(
        request,
        monkeypatch,
        store=InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: URL}),
        running=running,
    )


def assert_no_secret(text: str, where: str) -> None:
    for part in SECRET_PARTS:
        assert part not in text, f"{part!r} leaked into {where}"
