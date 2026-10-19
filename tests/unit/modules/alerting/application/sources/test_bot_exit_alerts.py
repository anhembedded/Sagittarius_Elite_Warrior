"""`BOT-189` — a stop loss, a take profit or a price outside the range reaches the owner at once.

`BotAlertSource` over a recording publisher. The exits are the entry into STOPPING with the reason
the bot gave the stop, the range event of a bot that only holds, and the exchange-side protective
stop having run; each is one alert, and none of them is also a fill message.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_alert_source import (
    EXIT_ON_STOP,
    BotAlertSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.recording_alert_publisher import (
    RecordingAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_protective_stop_event import (
    BotProtectiveStopEvent,
    ProtectiveStopChange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_range_changed_event import (
    BotRangeChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.range_position import (
    RangePosition,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.sources.bot_source_world import (
    BOT,
    Bots,
    entry,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import build_rig


def _source(bots: Bots) -> tuple[BotAlertSource, RecordingAlertPublisher]:
    published = RecordingAlertPublisher()
    source = BotAlertSource(bots, published, FakeAlertClock())
    source.seed()
    return source, published


def _range(position: RangePosition, *, closes: bool = False) -> BotRangeChangedEvent:
    return BotRangeChangedEvent(
        bot_id=BOT,
        symbol="ETHUSDT",
        position=position,
        price=Decimal(2290),
        lower=Decimal(2300),
        upper=Decimal(2700),
        closes=closes,
    )


@pytest.mark.parametrize(
    ("reason", "kind", "severity"),
    [
        (GridReason.STOP_LOSS, AlertKind.STOP_LOSS_HIT, Severity.CRITICAL),
        (GridReason.TAKE_PROFIT, AlertKind.TAKE_PROFIT_HIT, Severity.CRITICAL),
        (GridReason.RANGE_EXIT, AlertKind.RANGE_EXIT, Severity.CRITICAL),
    ],
)
def test_a_stop_that_began_with_an_exit_reason_is_one_loud_alert_at_once(
    reason: GridReason, kind: AlertKind, severity: Severity
) -> None:
    bots = Bots(entry("RUNNING"))
    source, published = _source(bots)

    bots.move("STOPPING", reason.value, "price 2290.5, traded to 2288")
    source.on_bot_changed(BotChangedEvent(bot_id=BOT))
    source.on_bot_changed(BotChangedEvent(bot_id=BOT))  # a rewrite: same state

    [alert] = published.published
    assert (alert.kind, alert.severity) == (kind, severity)
    assert "price 2290.5, traded to 2288" in alert.detail
    assert "closing its position at market" in alert.detail


def test_every_exit_reason_the_source_names_is_a_grid_reason() -> None:
    assert {reason.value for reason in GridReason} >= set(EXIT_ON_STOP)


def test_a_stop_the_owner_asked_for_is_not_an_exit() -> None:
    bots = Bots(entry("RUNNING"))
    source, published = _source(bots)

    bots.move("STOPPING", GridReason.USER_STOP.value)
    source.on_bot_changed(BotChangedEvent(bot_id=BOT))

    assert published.published == []


def test_a_price_below_the_range_of_a_bot_that_holds_is_one_warning_that_says_it_waits() -> (
    None
):
    source, published = _source(Bots(entry("RUNNING")))

    source.on_range_changed(_range(RangePosition.BELOW))

    [alert] = published.published
    assert (alert.kind, alert.severity) == (AlertKind.RANGE_EXIT, Severity.WARNING)
    assert "below the range 2300-2700" in alert.detail
    assert "keeps its orders" in alert.detail


def test_a_bot_that_closes_outside_the_range_is_told_by_its_stop_not_twice() -> None:
    source, published = _source(Bots(entry("RUNNING")))

    source.on_range_changed(_range(RangePosition.BELOW, closes=True))

    assert published.published == []


def test_the_return_inside_the_range_is_not_told() -> None:
    source, published = _source(Bots(entry("RUNNING")))
    source.on_range_changed(_range(RangePosition.BELOW))
    published.published.clear()

    source.on_range_changed(_range(RangePosition.INSIDE))

    assert published.published == []
    assert published.cleared == []


def test_a_price_that_flaps_at_the_edge_is_one_message_per_window_not_a_stream(
    tmp_path: Path,
) -> None:
    """The hub's 15 minute window for a WARNING is what bounds it; each crossing is an event."""
    rig = build_rig(tmp_path, channel_ids=("phone",))
    source = BotAlertSource(Bots(entry("RUNNING")), rig.hub, rig.clock)
    for _ in range(5):
        source.on_range_changed(_range(RangePosition.BELOW))
        source.on_range_changed(_range(RangePosition.INSIDE))
    rig.deliver_all()
    assert rig.received_kinds("phone") == [AlertKind.RANGE_EXIT]

    rig.clock.advance(timedelta(minutes=16))
    source.on_range_changed(_range(RangePosition.BELOW))
    rig.deliver_all()

    assert rig.received_kinds("phone") == [AlertKind.RANGE_EXIT] * 2


def test_leaving_on_the_other_side_is_a_new_alert_not_a_repeat() -> None:
    source, published = _source(Bots(entry("RUNNING")))

    source.on_range_changed(_range(RangePosition.BELOW))
    source.on_range_changed(_range(RangePosition.ABOVE))

    below, above = published.published
    assert below.dedup_key != above.dedup_key


def test_the_exchange_side_stop_having_run_is_a_stop_loss_alert() -> None:
    source, published = _source(Bots(entry("RUNNING")))

    source.on_protective_stop(
        BotProtectiveStopEvent(
            BOT, "ETHUSDT", ProtectiveStopChange.TRIGGERED, "filled at 2290"
        )
    )
    source.on_protective_stop(
        BotProtectiveStopEvent(
            BOT, "ETHUSDT", ProtectiveStopChange.MISSING, "not on the book"
        )
    )

    [alert] = published.published
    assert alert.kind is AlertKind.STOP_LOSS_HIT
    assert "filled at 2290" in alert.detail
