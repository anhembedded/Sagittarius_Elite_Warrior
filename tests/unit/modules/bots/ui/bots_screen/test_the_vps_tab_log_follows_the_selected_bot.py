"""`EPIC-047F` - the VPS tab's log panel shows the selected bot's own lines from the host, read-only, one bot at a time.

The feed is the real `RemoteBotLogFeed` over the real `BotsViewModel`; the host is a function shaped like `IVpsTab.bot_log`, and
the pool is the screen's own test pool that holds a task until the test runs it.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_log_chunk import (
    BotLogChunk,
    BotLogLineOfTheHost,
    BotLogUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.remote_bot_log_feed import (
    POLL_MS,
    RemoteBotLogFeed,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.bots_screen.bots_screen_fixtures import (
    HeldPool,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    minimal_bot,
)

_ONE = replace(minimal_bot(), bot_id="ab12cd")
_TWO = replace(minimal_bot(), bot_id="zz99yy")


class Host:
    """The host's logs by bot, and every ask it was given."""

    def __init__(self) -> None:
        self.logs: dict[str, list[BotLogLineOfTheHost]] = {}
        self.asked: list[tuple[str, int]] = []
        self.down: BotLogUnavailableError | None = None

    def say(self, bot_id: str, seq: int, text: str, at: datetime | None = None) -> None:
        moment = (at or datetime.now(UTC)).isoformat(timespec="seconds")
        self.logs.setdefault(bot_id, []).append(
            BotLogLineOfTheHost(seq, moment, "INFO", text)
        )

    def read(self, bot_id: str, since: int) -> BotLogChunk:
        self.asked.append((bot_id, since))
        if self.down is not None:
            raise self.down
        lines = tuple(x for x in self.logs.get(bot_id, []) if x.seq > since)
        return BotLogChunk(lines, lines[-1].seq if lines else since)


class Setup:
    def __init__(self) -> None:
        self.host = Host()
        self.pool = HeldPool()
        self.model = BotsViewModel()
        self.now = datetime.now(UTC)
        self.feed = RemoteBotLogFeed(self.host.read, self.pool, lambda: self.now)
        self.feed.feed_model(self.model)

    def select(self, bot: object) -> None:
        self.model.set_selected(bot)  # type: ignore[arg-type]

    def settle(self) -> None:
        self.pool.run_all()


@pytest.fixture
def setup(qtbot: object) -> Setup:
    made = Setup()
    made.feed.setParent(None)
    return made


def test_selecting_a_bot_shows_its_own_lines_newest_last_with_the_hosts_words(
    setup: Setup,
) -> None:
    setup.host.say("ab12cd", 1, "fill of 0.5 [exit-closed]")
    setup.host.say("ab12cd", 2, "waiting for the price")

    setup.select(_ONE)
    setup.settle()

    shown = setup.model.selected_log()
    assert [line.split(" ", 2)[1:] for line in shown] == [
        ["INFO", "Bot ab12cd: fill of 0.5 [exit-closed]"],
        ["INFO", "Bot ab12cd: waiting for the price"],
    ]


def test_only_the_selected_bots_log_is_ever_asked_for(setup: Setup) -> None:
    setup.host.say("ab12cd", 1, "mine")
    setup.host.say("zz99yy", 2, "theirs")

    setup.select(_ONE)
    setup.settle()
    setup.select(_TWO)
    setup.settle()

    assert {bot_id for bot_id, _since in setup.host.asked} == {"ab12cd", "zz99yy"}
    assert [t for t in setup.model.selected_log() if "mine" in t] == []
    assert any("theirs" in t for t in setup.model.selected_log())


def test_nothing_is_asked_while_no_bot_is_selected(setup: Setup) -> None:
    setup.feed._ask_for_the_log()
    setup.settle()

    assert setup.host.asked == []


def test_the_next_ask_starts_from_the_cursor_and_a_line_is_never_shown_twice(
    setup: Setup,
) -> None:
    setup.host.say("ab12cd", 5, "first")
    setup.select(_ONE)
    setup.settle()
    setup.host.say("ab12cd", 9, "second")

    setup.feed._ask_for_the_log()
    setup.settle()
    setup.select(_TWO)
    setup.settle()
    setup.select(_ONE)
    setup.settle()

    assert ("ab12cd", 5) in setup.host.asked
    assert ("ab12cd", 9) in setup.host.asked
    texts = [t for t in setup.model.selected_log()]
    assert len([t for t in texts if "first" in t]) == 1
    assert len([t for t in texts if "second" in t]) == 1


def test_a_late_answer_for_a_bot_no_longer_selected_is_dropped(setup: Setup) -> None:
    setup.host.say("ab12cd", 1, "for the first bot")
    setup.select(_ONE)
    setup.select(_TWO)
    setup.settle()

    assert setup.model.selected is _TWO
    assert [t for t in setup.model.selected_log() if "first bot" in t] == []
    model_lines = list(setup.model._log)
    assert [t for t in model_lines if "first bot" in t] == []


def test_an_answer_that_arrives_after_the_bot_was_deselected_is_dropped(
    setup: Setup,
) -> None:
    setup.host.say("ab12cd", 1, "too late")
    setup.select(_ONE)
    setup.select(None)
    setup.settle()

    assert list(setup.model._log) == []


def test_a_second_ask_waits_while_the_first_is_in_flight(setup: Setup) -> None:
    setup.select(_ONE)

    setup.feed._ask_for_the_log()
    setup.feed._ask_for_the_log()

    assert len(setup.pool.pending) == 1


def test_the_age_of_the_last_line_is_said_by_the_minute(setup: Setup) -> None:
    setup.host.say("ab12cd", 1, "old", at=setup.now - timedelta(minutes=7))
    setup.select(_ONE)
    setup.settle()

    assert "7 min old" in setup.model.log_note

    setup.host.say("ab12cd", 2, "new", at=setup.now)
    setup.feed._ask_for_the_log()
    setup.settle()

    assert "under a minute" in setup.model.log_note


def test_a_host_that_cannot_be_read_is_told_in_its_words_and_the_lines_stay(
    setup: Setup,
) -> None:
    setup.host.say("ab12cd", 1, "kept")
    setup.select(_ONE)
    setup.settle()
    setup.host.down = BotLogUnavailableError("Not connected to the host.")

    setup.feed._ask_for_the_log()
    setup.settle()

    assert "Not connected to the host." in setup.model.log_note
    assert any("kept" in t for t in setup.model.selected_log())


def test_a_closed_feed_asks_nothing_more_and_the_timer_stops(setup: Setup) -> None:
    setup.select(_ONE)
    setup.settle()
    asked = len(setup.host.asked)

    setup.feed.close()
    setup.feed._ask_for_the_log()
    setup.settle()

    assert len(setup.host.asked) == asked
    assert not setup.feed._timer.isActive()


def test_the_poll_interval_is_a_few_seconds_not_a_stream() -> None:
    assert 1000 <= POLL_MS <= 10000
