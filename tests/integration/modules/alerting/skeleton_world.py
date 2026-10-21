"""The walking skeleton's world: the composed app over fake Discord and a fake market stream.

Shared by the journeys that send an alert through the graph `create_app()` builds
(`test_a_halted_bot_reaches_discord.py`, `test_a_stalled_price_feed_reaches_discord.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.wake_signal import (
    WakeSignal,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.composition.channel_bindings import (
    ChannelSecrets,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
    RecordedPost,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.contract_bot_store import (
    sample_bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import BotLifecycle
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.tests.discord_posts import posts_without_heartbeat
from Sagittarius_Elite_Warrior.tests.integration.modules.bots.bots_module_world import (
    GRID_CONFIG,
)
from Sagittarius_Elite_Warrior.tests.integration.modules.bots.grid_fake_exchange import (
    FakeStreamSources,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore
from sagittarius_engine import App
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

WAIT_S = 15.0
TOKEN = "Sk3l3t0n-T0ken_xyz"  # noqa: S105 - a made-up token the leak check looks for
WEBHOOK = f"https://discord.com/api/webhooks/998877/{TOKEN}"


@dataclass
class Skeleton:
    app: App
    transport: FakeWebhookTransport
    clock: FakeAlertClock

    def save(self, state: BotLifecycleState) -> None:
        """Write the sample bot in `state` through the bots' own store."""
        stored = sample_bot()
        definition = replace(stored.bot.definition, config=GRID_CONFIG)
        bot = replace(stored.bot, definition=definition, lifecycle=BotLifecycle(state))
        store = self.app.container.resolve(IBotStore)  # type: ignore[type-abstract]
        store.save(replace(stored, bot=bot, runtime={}))

    @property
    def posts(self) -> list[RecordedPost]:
        """What the channel was sent, without the heartbeat the booted app sends on its own
        (`BUG-252`): a journey is about the alert it raises."""
        return posts_without_heartbeat(self.transport)

    def wait_for_posts(self, count: int) -> None:
        while len(self.posts) < count:
            self.transport.posted.clear()
            if len(self.posts) >= count:
                return
            assert self.transport.posted.wait(WAIT_S), f"no POST #{count}"

    def nudge_after(self, wait: timedelta) -> None:
        """Move the alert clock and wake the lanes, as their poll would."""
        self.clock.advance(wait)
        self.app.container.resolve(WakeSignal).notify()


def boot_skeleton(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    store: InMemorySecretStore,
    transport: FakeWebhookTransport,
) -> Skeleton:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))
    clock = FakeAlertClock()
    transport.clock = clock.now
    app = create_app(ConfigManager())
    container = app.container
    container.singleton(ChannelSecrets, ChannelSecrets(store))
    container.singleton(IWebhookTransport, transport)
    container.singleton(IAlertClock, clock)
    real_sources = container.resolve(IMarketDataSources)  # type: ignore[type-abstract]
    container.singleton(
        IMarketDataSources, FakeStreamSources(real_sources, FakeMarketStream())
    )
    app.boot()
    return Skeleton(app, transport, clock)
