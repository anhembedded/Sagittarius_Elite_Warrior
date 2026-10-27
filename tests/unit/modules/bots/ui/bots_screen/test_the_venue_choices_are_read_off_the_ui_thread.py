"""`EPIC-048B` — the venues a bot may be on are read on the thread manager, held, and offered.

Whether a venue has a saved API key is a host fact (DERISK §8.1): reading it on the UI thread,
as `venue_choice.py` once did, would stall the screen behind a remote backend's link. The screen
asks `GetVenueChoicesQuery` as a fenced read of its own (`ReadKind.VENUES`) when it opens, after
every command and on its clock, and New bot offers what it holds: the click reads nothing, so a
dispatch that fails at the click (`test_bots_failures.py`) cannot reach it.
"""

from __future__ import annotations

from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_choices import (
    GetVenueChoicesQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_venues import (
    NOT_READ_YET,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_failures import (
    read_cause,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.venue_choice import (
    KEY_SAVED,
)

from .bots_screen_fixtures import (
    VENUE,
    BotsScreen,
    ContainerDispatcher,
    HeldPool,
    stored,
)


class _Where:
    """Records, for each venues read, whether the pool was running a task."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.in_pool = False
        self.reads: list[bool] = []
        run, dispatch = HeldPool.run, ContainerDispatcher.dispatch
        where = self

        def pooled(pool: HeldPool, index: int) -> None:
            where.in_pool = True
            try:
                run(pool, index)
            finally:
                where.in_pool = False

        def recorded(
            dispatcher: ContainerDispatcher,
            handler_class: type,
            input_dto: object | None = None,
        ) -> Any:
            if handler_class is GetVenueChoicesQuery:
                where.reads.append(where.in_pool)
            return dispatch(dispatcher, handler_class, input_dto)

        monkeypatch.setattr(HeldPool, "run", pooled)
        monkeypatch.setattr(ContainerDispatcher, "dispatch", recorded)


def _venue_reads(screen: BotsScreen) -> int:
    """A pooled read is `(FencedReads._read_on_pool, (kind, action_id, label, task))`."""
    return sum(
        1 for _, args in screen.pool.pending if args and args[0] is ReadKind.VENUES
    )


def test_the_venues_are_read_on_the_pool_when_the_screen_opens(
    open_bots_screen, monkeypatch: pytest.MonkeyPatch
) -> None:
    where = _Where(monkeypatch)
    screen = open_bots_screen([])

    assert screen.view.model.venue_choices == ()
    assert _venue_reads(screen) == 1

    screen.settle()

    assert where.reads == [True]
    first = screen.view.model.venue_choices[0]
    assert (first.venue, first.connection) == (VENUE, KEY_SAVED)


def test_new_bot_offers_the_venues_held_and_reads_nothing_at_the_click(
    open_bots_screen, monkeypatch: pytest.MonkeyPatch
) -> None:
    where = _Where(monkeypatch)
    screen = open_bots_screen([])
    screen.settle()
    held = screen.view.model.venue_choices
    asked = len(where.reads)

    screen.view.model.new_bot_requested.emit()

    assert len(where.reads) == asked
    assert screen.pool.pending == []
    assert screen.answers.offered == [choice.option_text for choice in held]


def test_a_command_reads_the_venues_again(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    screen.view.model.select_requested.emit("a00001")
    screen.settle()

    assert screen.pool.pending == []

    screen.view.model.action_requested.emit(BotAction.SAVE.value)
    screen.pool.run(0)  # the command alone; its answer asks again

    assert _venue_reads(screen) == 1


def test_the_screens_clock_reads_the_venues_again(open_bots_screen) -> None:
    """A key saved in Settings shows within a beat, not only after the next command."""
    screen = open_bots_screen([])
    screen.settle()

    screen.presenter._clock.timeout.emit()

    assert _venue_reads(screen) == 1


def test_a_venues_read_that_failed_is_one_message_bar_with_retry(
    open_bots_screen, monkeypatch: pytest.MonkeyPatch
) -> None:
    dispatch = ContainerDispatcher.dispatch

    def refused(
        dispatcher: ContainerDispatcher,
        handler_class: type,
        input_dto: object | None = None,
    ) -> Any:
        if handler_class is GetVenueChoicesQuery:
            raise ConnectionError("the link dropped")
        return dispatch(dispatcher, handler_class, input_dto)

    monkeypatch.setattr(ContainerDispatcher, "dispatch", refused)
    screen = open_bots_screen([])
    screen.settle()

    (notice,) = [
        failure
        for failure in screen.notifier.failures
        if failure.cause == read_cause(ReadKind.VENUES)
    ]
    assert notice.kind is FailureKind.BACKGROUND
    assert "the link dropped" not in notice.headline
    assert notice.retry is not None
    assert screen.view.model.venue_choices == ()

    monkeypatch.setattr(ContainerDispatcher, "dispatch", dispatch)
    notice.retry()
    screen.settle()

    assert screen.view.model.venue_choices[0].connection == KEY_SAVED


def test_new_bot_before_the_first_answer_opens_no_empty_dialog(
    open_bots_screen,
) -> None:
    """Nothing read yet: the dialog would hold no venue, so it is not opened, the screen says
    why, and the venues are asked again."""
    screen = open_bots_screen([])

    screen.view.model.new_bot_requested.emit()

    assert "new bot" not in screen.answers.asked
    assert screen.view.model.statusMessage == NOT_READ_YET
    assert _venue_reads(screen) == 2  # the one from opening, and the ask the click made

    screen.settle()
    screen.view.model.new_bot_requested.emit()

    assert screen.answers.offered


def test_new_bot_after_a_failed_read_opens_no_empty_dialog(
    open_bots_screen, monkeypatch: pytest.MonkeyPatch
) -> None:
    dispatch = ContainerDispatcher.dispatch

    def refused(
        dispatcher: ContainerDispatcher,
        handler_class: type,
        input_dto: object | None = None,
    ) -> Any:
        if handler_class is GetVenueChoicesQuery:
            raise ConnectionError("the link dropped")
        return dispatch(dispatcher, handler_class, input_dto)

    monkeypatch.setattr(ContainerDispatcher, "dispatch", refused)
    screen = open_bots_screen([])
    screen.settle()

    screen.view.model.new_bot_requested.emit()

    assert screen.answers.offered == []
    assert screen.view.model.statusMessage == NOT_READ_YET
