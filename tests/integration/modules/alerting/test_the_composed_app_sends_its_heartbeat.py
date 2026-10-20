"""The graph `create_app()` builds sends a heartbeat to Discord at boot (`EPIC-036E`).

A test that constructs `HeartbeatService` proves the service, not that the application binds it
to the housekeeping thread and starts that thread (`CS-002`): this boots the real composition
with a stored webhook and the network boundary replaced by a fake transport.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_webhook_channel import (
    DISCORD_WEBHOOK_SECRET,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.composition.channel_bindings import (
    ChannelSecrets,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore
from sagittarius_engine import App
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

WAIT_S = 15.0
WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/abcDEF-ghi_JKL"


@pytest.fixture(autouse=True)
def _data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))
    return tmp_path


@pytest.fixture
def booted() -> Iterator[tuple[App, FakeWebhookTransport]]:
    transport = FakeWebhookTransport()
    app = create_app(ConfigManager())
    app.container.singleton(
        ChannelSecrets,
        ChannelSecrets(InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK})),
    )
    app.container.singleton(IWebhookTransport, transport)
    app.boot()
    try:
        yield app, transport
    finally:
        app.stop()


def test_a_booted_app_with_a_webhook_sends_a_heartbeat_to_it(
    booted: tuple[App, FakeWebhookTransport],
) -> None:
    _app, transport = booted

    assert transport.posted.wait(WAIT_S)
    assert transport.posts[0].url == WEBHOOK
    assert "Heartbeat" in str(transport.posts[0].body["content"])
