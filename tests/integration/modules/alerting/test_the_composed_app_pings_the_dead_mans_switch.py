"""The graph `create_app()` builds starts the dead man's switch when a check-in URL is
stored, and the ping is a POST to exactly that URL (`EPIC-036E1`, N7).

A test that constructs `DeadMansSwitch` proves the switch, not that the application binds
it to the worker and starts its beacon at boot (`CS-002`): this boots the real
composition with the network boundary replaced by a fake transport.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.alerting.application.dead_mans_switch import (
    DEAD_MANS_SWITCH_SECRET,
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
URL = "https://hc-ping.com/0d9b6e7c-52a1-4f0e-9a3b-6c1d2e3f4a5b"


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
        ChannelSecrets(InMemorySecretStore(**{DEAD_MANS_SWITCH_SECRET: URL})),
    )
    app.container.singleton(IWebhookTransport, transport)
    app.boot()
    try:
        yield app, transport
    finally:
        app.stop()


def test_a_booted_app_with_a_check_in_url_pings_it(
    booted: tuple[App, FakeWebhookTransport],
) -> None:
    _app, transport = booted

    assert transport.posted.wait(WAIT_S)
    assert transport.posts[0].url == URL
