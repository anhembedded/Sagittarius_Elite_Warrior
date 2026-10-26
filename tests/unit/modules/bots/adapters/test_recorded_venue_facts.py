"""`EPIC-047B` - the readiness reads are recorded as they happen, and nothing else is asked."""

from __future__ import annotations

import threading

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.latest_venue_reads import (
    LatestVenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.recorded_venue_facts import (
    RecordedVenueFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeLoaded,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    BotExchangeRead,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_facts import (
    IVenueFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import seed
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.host_facts.host_facts_world import (
    spot_facts,
)


class ScriptedVenueFacts(IVenueFacts):
    def __init__(self, *answers: VenueSnapshot | Exception) -> None:
        self._answers = list(answers)
        self.asked: list[str] = []

    def read(self, bot: Bot) -> VenueSnapshot:
        self.asked.append(bot.bot_id.value)
        answer = self._answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _bot(bot_id: str) -> Bot:
    return seed(FakeBotStore(), bot_id, BotLifecycleState.RUNNING)


def test_the_caller_gets_the_inner_readers_answer_unchanged() -> None:
    loaded = ExchangeLoaded(spot_facts())
    recorded = RecordedVenueFacts(ScriptedVenueFacts(loaded), LatestVenueReads())

    assert recorded.read(_bot("aaaaaa")) is loaded


def test_each_read_is_remembered_for_its_bot_and_the_latest_wins() -> None:
    reads = LatestVenueReads()
    first, second = ExchangeUnavailable("first"), ExchangeLoaded(spot_facts())
    recorded = RecordedVenueFacts(ScriptedVenueFacts(first, second), reads)

    recorded.read(_bot("aaaaaa"))
    recorded.read(_bot("aaaaaa"))

    assert reads.latest() == (BotExchangeRead("aaaaaa", second),)


def test_recording_asks_the_inner_reader_exactly_once_per_read() -> None:
    """The tap adds no read: the exchange is asked as often as it was without it."""
    inner = ScriptedVenueFacts(ExchangeUnavailable("x"), ExchangeUnavailable("y"))
    recorded = RecordedVenueFacts(inner, LatestVenueReads())

    recorded.read(_bot("aaaaaa"))
    recorded.read(_bot("bbbbbb"))

    assert inner.asked == ["aaaaaa", "bbbbbb"]


def test_a_read_that_raises_raises_the_same_and_records_nothing() -> None:
    reads = LatestVenueReads()
    recorded = RecordedVenueFacts(ScriptedVenueFacts(RuntimeError("boom")), reads)

    with pytest.raises(RuntimeError, match="boom"):
        recorded.read(_bot("aaaaaa"))

    assert reads.latest() == ()


def test_the_latest_reads_are_listed_in_bot_order() -> None:
    reads = LatestVenueReads()
    for bot_id in ("cccccc", "aaaaaa", "bbbbbb"):
        reads.record(bot_id, ExchangeUnavailable(bot_id))

    assert [r.bot_id for r in reads.latest()] == ["aaaaaa", "bbbbbb", "cccccc"]


def test_recording_from_many_threads_loses_no_bot() -> None:
    reads = LatestVenueReads()

    def record(index: int) -> None:
        for round_ in range(50):
            reads.record(f"bot{index:02d}", ExchangeUnavailable(str(round_)))
            reads.latest()

    threads = [threading.Thread(target=record, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(reads.latest()) == 8
