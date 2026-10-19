"""`BOT-189` — the bound on fill messages, and a CRITICAL that never waits behind them.

The real hub, outbox and worker pass over a fake channel and clock. Nothing here claims a Discord
rate: what is measured is what *this* code does when a channel stops taking messages while a grid
keeps filling — how many fill messages are kept, that the rest become one line, and that the next
message the channel takes is the CRITICAL one.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DeliveryPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    Rig,
    an_alert,
    bot_subject,
    build_rig,
    states_of,
)

KEEP = DeliveryPolicy().fill_backlog


def _fill(rig: Rig, number: int, bot_id: str = "g3n092") -> None:
    rig.hub.publish(
        an_alert(
            AlertKind.ORDER_FILLED,
            bot_subject(bot_id),
            reason=f"order-{number}",
            at=rig.clock.now(),
        )
    )


def _received_fills(rig: Rig) -> list[str]:
    return [
        item.alert.dedup_key.rsplit(":", 1)[1]
        for item in rig.channels["phone"].received
        if item.alert.kind is AlertKind.ORDER_FILLED
    ]


def test_a_fill_message_is_sent_silent_one_per_order(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))

    for number in range(3):
        _fill(rig, number)
    rig.deliver_all()

    assert _received_fills(rig) == ["order-0", "order-1", "order-2"]
    assert {item.loudness for item in rig.channels["phone"].received} == {
        Loudness.SILENT
    }


def test_past_the_bound_the_oldest_fill_messages_are_dropped_and_said_once(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    published = KEEP + 5

    for number in range(published):
        _fill(rig, number)
    assert rig.outbox.pending_count("phone") == KEEP

    rig.hub.flush_due()
    rig.hub.flush_due()  # the second tick finds nothing new to say
    rig.deliver_all()

    assert _received_fills(rig) == [f"order-{n}" for n in range(5, published)]
    skipped = [
        item.alert
        for item in rig.channels["phone"].received
        if item.alert.kind is AlertKind.FILLS_SKIPPED
    ]
    [line] = skipped
    assert line.title == "5 fill messages skipped"
    dropped = [s for s in states_of(rig, "phone") if s is DeliveryState.DROPPED]
    assert len(dropped) == 5


def test_a_critical_is_the_first_message_a_channel_takes_after_a_wait_behind_a_burst_of_fills(
    tmp_path: Path,
) -> None:
    """A channel asks to wait while the grid keeps filling: 60 fills are published, 25 are kept,
    35 become one line, and the first message sent when the channel takes messages again is the
    CRITICAL that arrived last."""
    rig = build_rig(tmp_path, channel_ids=("phone",))
    wait = timedelta(seconds=5)
    rig.channels["phone"].script = [DeliveryResult.retry_later(wait, "rate limited")]
    _fill(rig, 0)
    rig.deliver_all()  # the channel answers 429 for the whole lane
    assert rig.channels["phone"].received[0].alert.kind is AlertKind.ORDER_FILLED

    for number in range(1, 60):
        _fill(rig, number)
    rig.hub.publish(an_alert(AlertKind.STOP_LOSS_HIT, at=rig.clock.now()))
    rig.hub.flush_due()
    rig.deliver_all()  # still waiting: nothing is tried
    assert len(rig.channels["phone"].received) == 1

    rig.clock.advance(wait)
    rig.deliver_all()

    after_the_wait = [item.alert for item in rig.channels["phone"].received[1:]]
    assert after_the_wait[0].kind is AlertKind.STOP_LOSS_HIT
    assert [
        a.dedup_key.rsplit(":", 1)[1]
        for a in after_the_wait
        if a.kind is AlertKind.ORDER_FILLED
    ] == [f"order-{n}" for n in range(60 - KEEP, 60)]
    [line] = [a for a in after_the_wait if a.kind is AlertKind.FILLS_SKIPPED]
    assert line.title == f"{60 - KEEP} fill messages skipped"


def test_a_bot_set_to_critical_only_or_off_sends_no_fill_messages(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    rig.settings.replace(
        AlertSettings(
            bot_modes={
                "quiet": BotAlertMode.CRITICAL_ONLY,
                "muted": BotAlertMode.OFF,
            }
        )
    )

    _fill(rig, 1, bot_id="quiet")
    _fill(rig, 2, bot_id="muted")
    _fill(rig, 3, bot_id="loud")
    rig.deliver_all()

    assert _received_fills(rig) == ["order-3"]
