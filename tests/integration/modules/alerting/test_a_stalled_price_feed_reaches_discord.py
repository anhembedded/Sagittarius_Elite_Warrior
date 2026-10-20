"""`EPIC-036B2` — a bot's price feed that stays quiet reaches Discord as one `PRICE_FEED_STALE`,
on the graph `create_app()` builds (the module subscribed `BotRecoveryStalledEvent`, the source
routed its reason, the hub grouped it, the real Discord channel posted it)."""

from __future__ import annotations

from datetime import timedelta
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_recovery_stalled_event import (
    BotRecoveryStalledEvent,
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

#: The harness bot halts meanwhile (one post); the feed alert is the other.
_MOST_POSTS_BEFORE_THE_FEED_ALERT = 3


def _feed_alerts(booted: Skeleton) -> list[str]:
    return [
        str(post.body["content"])
        for post in booted.transport.posts
        if "Price feed stale: grid one" in str(post.body["content"])
    ]


def test_a_quiet_price_feed_that_stalled_a_wait_reaches_discord_as_one_critical_alert(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`EPIC-036B2`: the same event with the price feed's reason is the `PRICE_FEED_STALE` kind.
    The hub groups a feed alert for ten seconds, so the owner's clock is moved past the window;
    the harness bot also halts meanwhile, which is why the post is looked for, not counted."""
    booted = boot_skeleton(
        monkeypatch,
        tmp_path,
        InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK}),
        FakeWebhookTransport(),
    )
    events = booted.app.container.resolve(IEventPublisher)  # type: ignore[type-abstract]
    try:
        booted.save(BotLifecycleState.DRAFT)
        booted.save(BotLifecycleState.AWAITING_RECOVERY)
        events.publish(
            BotRecoveryStalledEvent(
                bot_id="abc123", reason="price_feed_stale", waited_s=900
            )
        )
        booted.nudge_after(timedelta(seconds=11))
        for expected in range(1, _MOST_POSTS_BEFORE_THE_FEED_ALERT + 1):
            booted.wait_for_posts(expected)
            if _feed_alerts(booted):
                break
    finally:
        booted.app.stop()

    [stale] = _feed_alerts(booted)
    assert "CRITICAL" in stale
    assert "cannot watch its stop loss" in stale
