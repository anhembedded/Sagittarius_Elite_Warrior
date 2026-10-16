"""`EPIC-036G` — a bot entering HALTED or ERROR, or whose stop gave up, becomes
exactly one CRITICAL alert; a rewrite is not a second one; a restart re-alerts
nothing; a return to RUNNING clears the condition."""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

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
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_stop_retry import (
    STOP_RETRY_DELAYS,
)
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
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import build_rig

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


class _InterleavingBots(_Bots):
    """A second writer's event arrives while the first one's read is under way:
    the store moves to `then` and that writer's handler runs, before the first
    read returns what it saw."""

    def __init__(self, entry: BotStatusEntry, then: str) -> None:
        super().__init__(entry)
        self.then = then
        self.source: BotAlertSource | None = None
        self._interleaved = False

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        seen = super().dispatch(handler_class, input_dto)
        reads_one_bot = (
            isinstance(input_dto, GetBotStatusReportQuery) and input_dto.bot_id
        )
        if reads_one_bot and not self._interleaved and self.source is not None:
            self._interleaved = True
            self.move(self.then)
            second = threading.Thread(
                target=self.source.on_bot_changed, args=(_changed(),)
            )
            second.start()
            second.join(timeout=_SECOND_WRITER_WAIT_S)
            self.second = second
        return seen


#: A bounded wait, not a timing assumption: with the read under the lock the second
#: writer cannot read before the first finishes, so the wait runs out; without it
#: the second writer is done long before. Either way the test then joins it.
_SECOND_WRITER_WAIT_S = 0.2


def test_a_second_writer_never_leaves_a_stale_remembered_state() -> None:
    """Review finding (PR #537): the read of the bot and the record of its state
    are one step, so a writer whose event comes second is judged on the state it
    leaves, not overtaken by the first writer's older read."""
    bots = _InterleavingBots(_entry("RUNNING"), then="RUNNING")
    source, published = _source(bots)
    bots.move("HALTED")
    bots._interleaved = False  # the seed's read is not the one under test
    bots.source = source

    source.on_bot_changed(
        _changed()
    )  # writer A read HALTED; writer B's RUNNING lands meanwhile
    bots.second.join()

    # A's halt is told, and B's return to RUNNING clears it: the last remembered
    # state is RUNNING, so the bot's next halt is an entry again.
    assert [a.kind for a in published.published] == [AlertKind.BOT_HALTED]
    assert published.cleared == [_key(AlertKind.BOT_HALTED), _key(AlertKind.BOT_ERROR)]
    bots.move("HALTED")
    source.on_bot_changed(_changed())
    assert [a.kind for a in published.published] == [
        AlertKind.BOT_HALTED,
        AlertKind.BOT_HALTED,
    ]


def test_a_second_round_that_gives_up_is_told_again_through_the_real_hub(
    tmp_path: Path,
) -> None:
    """Review question (PR #537): the hub's CRITICAL dedup window is one minute and
    a round of stop retries lasts longer, so the owner hears the second give-up."""
    rig = build_rig(tmp_path)
    source = BotAlertSource(_Bots(_entry("STOPPING")), rig.hub, rig.clock)
    source.seed()

    source.on_stop_gave_up(BotStopGaveUpEvent(bot_id=BOT, retries=5))
    rig.deliver_all()
    rig.clock.advance(
        sum(STOP_RETRY_DELAYS, timedelta())
    )  # the owner presses Stop again
    source.on_stop_gave_up(BotStopGaveUpEvent(bot_id=BOT, retries=5))
    rig.deliver_all()
    rig.outbox.close()

    assert rig.received_kinds("phone") == [AlertKind.STOP_FAILED, AlertKind.STOP_FAILED]
