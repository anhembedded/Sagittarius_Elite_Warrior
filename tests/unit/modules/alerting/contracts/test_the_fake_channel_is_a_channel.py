"""The fake channel answers as its script says, as a real channel would."""

from __future__ import annotations

from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel import (
    IAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_channel import (
    FakeAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import an_alert


def test_it_is_a_channel_and_sends_by_default() -> None:
    channel = FakeAlertChannel()

    assert isinstance(channel, IAlertChannel)
    assert channel.deliver(an_alert(), Loudness.LOUD) == DeliveryResult.sent()
    assert [(r.alert, r.loudness) for r in channel.received] == [
        (an_alert(), Loudness.LOUD)
    ]


def test_it_plays_its_script_then_falls_back_to_the_default() -> None:
    first = DeliveryResult.retry_later(timedelta(seconds=5), "slow down")
    channel = FakeAlertChannel(script=[first], default=DeliveryResult.failed("down"))

    assert channel.deliver(an_alert(), Loudness.SILENT) == first
    assert channel.deliver(an_alert(), Loudness.SILENT) == DeliveryResult.failed("down")


def test_a_scripted_exception_is_raised_after_the_message_was_seen() -> None:
    channel = FakeAlertChannel(default=ValueError("boom"))

    with pytest.raises(ValueError, match="boom"):
        channel.deliver(an_alert(), Loudness.LOUD)

    assert len(channel.received) == 1
