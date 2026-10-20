"""The graph `create_app()` builds moves an old config-file Telegram token into the secret store
at boot and then delivers an alert through it (`EPIC-036C1`, N3).

A test that constructs the migration and the channel proves each, not that the application runs
the migration before it builds its channels (`CS-002`): this boots the real composition with the
network boundary replaced by a fake transport and the config write by a recording writer (the
real one would write `user_config.json`).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.telegram_channel import (
    TELEGRAM_CHAT_SECRET,
    TELEGRAM_TOKEN_SECRET,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.composition.channel_bindings import (
    ChannelSecrets,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_publisher import (
    IAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
    WebhookResponse,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore
from sagittarius_engine import App
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

WAIT_S = 15.0
TOKEN = "987654321:Zq9-xY_wEbH00kT0k3nZq9xYwEbH00kT0k3n"  # noqa: S105 - made up
CHAT = "5550123"


class _RecordingWriter(IConfigWriter):
    def __init__(self, config: ConfigManager) -> None:
        self._config = config
        self.saves = 0

    def set(self, key: str, value: object) -> None:
        self._config.set(key, value)

    def save(self) -> None:
        self.saves += 1


@pytest.fixture(autouse=True)
def _data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))
    return tmp_path


@pytest.fixture
def booted() -> Iterator[
    tuple[App, FakeWebhookTransport, InMemorySecretStore, ConfigManager]
]:
    config = ConfigManager()
    config.set(ConfigKeys.NOTIFICATIONS_TELEGRAM_BOT_TOKEN.value, TOKEN)
    config.set(ConfigKeys.NOTIFICATIONS_TELEGRAM_CHAT_ID.value, CHAT)
    transport = FakeWebhookTransport(default=WebhookResponse(200))
    store = InMemorySecretStore()
    app = create_app(config)
    app.container.singleton(ChannelSecrets, ChannelSecrets(store))
    app.container.singleton(IWebhookTransport, transport)
    app.container.singleton(IConfigWriter, _RecordingWriter(config))
    app.boot()
    try:
        yield app, transport, store, config
    finally:
        app.stop()


def test_an_old_config_token_is_moved_at_boot_and_then_used_by_the_telegram_channel(
    booted: tuple[App, FakeWebhookTransport, InMemorySecretStore, ConfigManager],
) -> None:
    app, transport, store, config = booted

    app.container.resolve(IAlertPublisher).publish(  # type: ignore[type-abstract]
        Alert.raised(
            AlertKind.APP_FAILURE,
            AlertSubject.app(),
            "Something failed",
            "detail",
            datetime.now(UTC),
            "integration",
        )
    )

    assert transport.posted.wait(WAIT_S)
    assert store.secrets == {TELEGRAM_TOKEN_SECRET: TOKEN, TELEGRAM_CHAT_SECRET: CHAT}
    assert config.get(ConfigKeys.NOTIFICATIONS_TELEGRAM_BOT_TOKEN.value) == ""
    assert transport.posts[0].url == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert transport.posts[0].body["chat_id"] == CHAT
