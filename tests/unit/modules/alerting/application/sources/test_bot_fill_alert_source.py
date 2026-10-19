"""`BOT-189` — a bot's filled order becomes one INFO alert that names the order.

The source on its own, over a recording publisher: what it words, how it keys, and that the fill
which closes a cycle carries the cycle's figures.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_fill_alert_source import (
    BotFillAlertSource,
    fill_line,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.recording_alert_publisher import (
    RecordingAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_order_filled_event import (
    BotOrderFilledEvent,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.sources.bot_source_world import (
    BOT,
    Bots,
    entry,
)

D = Decimal


def _event(
    order_id: str = "o-1",
    cycle_profit: Decimal | None = None,
    price: str = "2393.17",
) -> BotOrderFilledEvent:
    return BotOrderFilledEvent(
        bot_id=BOT,
        order_id=order_id,
        side="BUY",
        price=D(price),
        quantity=D("0.0190"),
        level=7,
        realised_total=D("12.8"),
        completed_cycles=31,
        quote_asset="USDT",
        cycle_profit=cycle_profit,
    )


def _source() -> tuple[BotFillAlertSource, RecordingAlertPublisher]:
    published = RecordingAlertPublisher()
    return BotFillAlertSource(Bots(entry()), published, FakeAlertClock()), published


def test_a_filled_order_is_one_info_alert_naming_the_bot_and_the_fill() -> None:
    source, published = _source()

    source.on_order_filled(_event())

    [alert] = published.published
    assert alert.kind is AlertKind.ORDER_FILLED
    assert alert.severity is Severity.INFO
    assert alert.title == "Order filled: eth-grid"
    assert alert.subject.bot_id == BOT
    assert alert.detail == "ETHUSDT · BUY 0.019 @ 2,393.17 (level 7)"


def test_the_fill_that_closes_a_cycle_adds_the_cycle_the_total_and_the_count() -> None:
    source, published = _source()

    source.on_order_filled(_event(cycle_profit=D("0.41")))

    [alert] = published.published
    assert alert.detail.splitlines() == [
        "ETHUSDT · BUY 0.019 @ 2,393.17 (level 7)",
        "cycle +0.41 USDT · total +12.80 USDT · 31 cycles",
    ]


def test_a_losing_cycle_and_a_profit_under_a_cent_read_as_they_are() -> None:
    losing = fill_line(_event(cycle_profit=D("-1.5")), "ETHUSDT")
    tiny = fill_line(_event(cycle_profit=D("0.0042")), "ETHUSDT")

    assert "cycle -1.50 USDT" in losing
    assert "cycle +0.0042 USDT" in tiny


def test_the_order_with_the_bot_is_the_dedup_key() -> None:
    source, published = _source()

    source.on_order_filled(_event("o-1"))
    source.on_order_filled(_event("o-1"))
    source.on_order_filled(_event("o-2"))

    first, repeat, other = published.published
    assert first.dedup_key == repeat.dedup_key
    assert first.dedup_key != other.dedup_key
    assert BOT in first.dedup_key
    assert "o-1" in first.dedup_key


def test_a_fill_of_a_bot_the_report_no_longer_lists_is_still_told() -> None:
    published = RecordingAlertPublisher()
    source = BotFillAlertSource(Bots(), published, FakeAlertClock())

    source.on_order_filled(_event())

    [alert] = published.published
    assert alert.subject.bot_id == BOT
