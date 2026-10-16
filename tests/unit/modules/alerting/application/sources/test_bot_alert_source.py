"""`EPIC-036G` — a bot entering HALTED or ERROR, or whose stop gave up, becomes
exactly one CRITICAL alert; a rewrite is not a second one; a restart re-alerts
nothing; a return to RUNNING clears the condition."""

from __future__ import annotations

from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_alert_source import (
    ALERT_ON_ENTRY,
    CLEARED_ON_ENTRY,
    BotAlertSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.recording_alert_publisher import (
    RecordingAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
    BotStatusReport,
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_stop_gave_up_event import (
    BotStopGaveUpEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)

BOT = "g3n092"


class _Bots(ICommandDispatcher):
    """The bots' status report over a dict: the one query the source asks."""

    def __init__(self, *entries: BotStatusEntry) -> None:
        self.entries = {entry.bot_id: entry for entry in entries}

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        if handler_class is not GetBotStatusReportQuery or not isinstance(
            input_dto, GetBotStatusReportQuery
        ):
            raise AssertionError(f"the source asked for {handler_class!r}")
        if input_dto.bot_id is None:
            return BotStatusReport(bots=tuple(self.entries.values()))
        entry = self.entries.get(input_dto.bot_id)
        return BotStatusReport(bots=() if entry is None else (entry,))

    def move(self, state: str, reason: str = "") -> None:
        self.entries[BOT] = replace(self.entries[BOT], state=state, reason=reason)


def _entry(state: str = "RUNNING", reason: str = "") -> BotStatusEntry:
    return BotStatusEntry(
        bot_id=BOT,
        name="eth-grid",
        kind="grid",
        venue="spot_mainnet",
        symbol="ETHUSDT",
        state=state,
        reason=reason,
        run_started_at=None,
    )


def _source(bots: _Bots) -> tuple[BotAlertSource, RecordingAlertPublisher]:
    published = RecordingAlertPublisher()
    source = BotAlertSource(bots, published, FakeAlertClock())
    source.seed()
    return source, published


def _changed() -> BotChangedEvent:
    return BotChangedEvent(bot_id=BOT)


def _key(kind: AlertKind) -> str:
    subject = AlertSubject.bot(BOT, "eth-grid", "grid", "spot_mainnet", "ETHUSDT")
    return Alert.condition_key(kind, subject)


def test_entering_halted_publishes_one_critical_alert() -> None:
    bots = _Bots(_entry("RUNNING"))
    source, published = _source(bots)

    bots.move("HALTED", "price feed silent for 64 s")
    source.on_bot_changed(_changed())

    [alert] = published.published
    assert alert.kind is AlertKind.BOT_HALTED
    assert alert.severity is Severity.CRITICAL
    assert alert.subject == AlertSubject.bot(
        BOT, "eth-grid", "grid", "spot_mainnet", "ETHUSDT"
    )
    assert alert.title == "Bot halted: eth-grid"
    assert "price feed silent for 64 s" in alert.detail
    assert "RUNNING" in alert.detail
    assert alert.dedup_key == _key(AlertKind.BOT_HALTED)


def test_entering_error_publishes_bot_error() -> None:
    bots = _Bots(_entry("RUNNING"))
    source, published = _source(bots)

    bots.move("ERROR", "unexpected fault")
    source.on_bot_changed(_changed())

    assert [a.kind for a in published.published] == [AlertKind.BOT_ERROR]


def test_a_rewrite_of_a_halted_bot_publishes_nothing() -> None:
    bots = _Bots(_entry("RUNNING"))
    source, published = _source(bots)
    bots.move("HALTED")
    source.on_bot_changed(_changed())

    source.on_bot_changed(_changed())  # a fill booked, a reason edited: same state

    assert len(published.published) == 1


def test_seeding_at_boot_publishes_nothing() -> None:
    """A bot already HALTED when the app starts was alerted by the run that halted it."""
    bots = _Bots(_entry("HALTED", "earlier run"))
    source, published = _source(bots)

    source.on_bot_changed(_changed())

    assert published.published == []
    assert published.cleared == []


def test_a_return_to_running_clears_the_condition() -> None:
    bots = _Bots(_entry("RUNNING"))
    source, published = _source(bots)
    bots.move("HALTED")
    source.on_bot_changed(_changed())

    bots.move("RUNNING")
    source.on_bot_changed(_changed())

    assert published.cleared == [_key(AlertKind.BOT_HALTED), _key(AlertKind.BOT_ERROR)]


def test_a_stop_that_gave_up_publishes_stop_failed() -> None:
    bots = _Bots(_entry("STOPPING", "4 order(s) still open"))
    source, published = _source(bots)

    source.on_stop_gave_up(BotStopGaveUpEvent(bot_id=BOT, retries=5))

    [alert] = published.published
    assert alert.kind is AlertKind.STOP_FAILED
    assert alert.severity is Severity.CRITICAL
    assert "5 automatic retries" in alert.detail
    assert "4 order(s) still open" in alert.detail


def test_a_stop_that_gave_up_still_alerts_when_the_bot_cannot_be_read() -> None:
    """The alert that money may be on the exchange is not lost to a failed read."""
    source, published = _source(_Bots())

    source.on_stop_gave_up(BotStopGaveUpEvent(bot_id=BOT, retries=5))

    assert [a.subject.bot_id for a in published.published] == [BOT]


def test_a_stopped_bot_clears_its_stop_failed() -> None:
    bots = _Bots(_entry("STOPPING"))
    source, published = _source(bots)

    bots.move("STOPPED")
    source.on_bot_changed(_changed())

    assert published.cleared == [_key(AlertKind.STOP_FAILED)]


def test_a_removed_bot_is_forgotten() -> None:
    bots = _Bots(_entry("HALTED"))
    source, published = _source(bots)

    source.on_bot_changed(BotChangedEvent(bot_id=BOT, removed=True))
    bots.move("HALTED")
    source.on_bot_changed(_changed())  # the id came back: a new bot

    assert [a.kind for a in published.published] == [AlertKind.BOT_HALTED]


@pytest.mark.parametrize("state", [*ALERT_ON_ENTRY, *CLEARED_ON_ENTRY])
def test_every_state_the_source_names_is_a_lifecycle_state(state: str) -> None:
    """The source reads the contract's state text; a renamed state must fail here,
    not silence an alert."""
    assert BotLifecycleState(state).value == state
