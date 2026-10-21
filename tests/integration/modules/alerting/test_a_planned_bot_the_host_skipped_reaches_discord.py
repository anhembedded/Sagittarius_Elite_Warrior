"""`EPIC-045F` (ADR 045 D7) - a planned mainnet bot the host skipped reaches Discord, on the graph
`create_app()` builds (the module subscribed `PlannedBotNotStartedEvent`, the source built the alert,
the real Discord channel posted it). The unit test of the source calls its handler directly, so only
this one fails if the subscription line is deleted."""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_webhook_channel import (
    DISCORD_WEBHOOK_SECRET,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.planned_bot_not_started_event import (
    PlannedBotNotStartedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.tests.integration.modules.alerting.skeleton_world import (
    WEBHOOK,
    Skeleton,
    boot_skeleton,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore

#: The harness bot halts meanwhile (one post); the skip alert is the other.
_MOST_POSTS_BEFORE_THE_SKIP_ALERT = 3


def _skip_alerts(booted: Skeleton) -> list[str]:
    return [
        str(post.body["content"])
        for post in booted.posts
        if "Planned bot not started" in str(post.body["content"])
    ]


def test_a_skipped_planned_bot_reaches_discord_with_the_command_that_starts_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    booted = boot_skeleton(
        monkeypatch,
        tmp_path,
        InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK}),
        FakeWebhookTransport(),
    )
    events = booted.app.container.resolve(IEventPublisher)  # type: ignore[type-abstract]
    try:
        booted.save(BotLifecycleState.DRAFT)
        events.publish(
            PlannedBotNotStartedEvent(
                bot_id="abc123",
                venue="spot_mainnet",
                reason="--start-planned did not start bot abc123.",
            )
        )
        for expected in range(1, _MOST_POSTS_BEFORE_THE_SKIP_ALERT + 1):
            booted.wait_for_posts(expected)
            if _skip_alerts(booted):
                break
    finally:
        booted.app.stop()

    [alert] = _skip_alerts(booted)
    assert "WARNING" in alert
    assert "`bot start abc123 --confirm-venue spot_mainnet`" in alert
