"""`EPIC-029F` — the selected bot's log and the bots' log feed."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_log_feed import (
    BotLogFeed,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    LOG_LIMIT,
    BotsViewModel,
)

from .bots_screen_fixtures import stored


def _snapshot(bot_id: str) -> BotSnapshot:
    return BotSnapshot.of(stored(bot_id, BotLifecycleState.RUNNING).bot)


def test_the_log_shows_the_selected_bots_lines_only(qapp) -> None:
    model = BotsViewModel()
    model.set_selected(_snapshot("a00001"))
    model.append_log_line("12:00:00 INFO Bot a00001: ladder placed")
    model.append_log_line("12:00:01 INFO Bot b00002: ladder placed")
    model.append_log_line("12:00:02 INFO order SEW-a00001-0000000001 filled")

    assert model.selected_log() == ("12:00:00 INFO Bot a00001: ladder placed",)


def test_the_kept_lines_are_bounded(qapp) -> None:
    model = BotsViewModel()
    for index in range(LOG_LIMIT + 5):
        model.append_log_line(f"Bot a00001: line {index}")
    model.set_selected(_snapshot("a00001"))

    lines = model.selected_log()
    assert lines[0] == "Bot a00001: line 5"
    assert lines[-1] == f"Bot a00001: line {LOG_LIMIT + 4}"


def test_reselecting_the_same_bot_is_not_a_new_selection(qapp) -> None:
    model = BotsViewModel()
    heard: list[str] = []
    model.selection_changed.connect(lambda: heard.append("selection"))

    model.set_selected(_snapshot("a00001"))
    model.set_selected(_snapshot("a00001"))
    model.set_selected(None)

    assert heard == ["selection", "selection"]


def test_the_feed_copies_bots_info_lines_and_stops_when_closed(qtbot) -> None:
    feed = BotLogFeed()
    heard: list[str] = []
    feed.line.connect(heard.append)
    worker = logging.getLogger("App.Bots.Worker")

    with qtbot.waitSignal(feed.line, timeout=1000):
        worker.warning("Bot a00001: start ignored in RUNNING")
    worker.debug("Bot a00001: per-tick detail")
    feed.close()
    worker.warning("Bot a00001: after close")

    assert len(heard) == 1
    assert heard[0].endswith("WARNING Bot a00001: start ignored in RUNNING")
