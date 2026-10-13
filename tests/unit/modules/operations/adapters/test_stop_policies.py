"""The two stop policies (decision O1): leave the orders, or stop the bots first (`EPIC-038D`)."""

from __future__ import annotations

import logging
import threading

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.leave_orders_resting import (
    LeaveOrdersResting,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.stop_bots_first import (
    StopBotsFirst,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_policy import (
    StopLedger,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.stop_policy_world import (
    BotsWorld,
    ScriptedBot,
)

_LOGGER = "App.Operations.StopPolicy"


def _infos(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def test_leave_orders_resting_places_and_cancels_nothing_and_says_what_it_leaves(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = BotsWorld(
        [
            ScriptedBot("aaaaaa", ["RUNNING"], resting_orders=4),
            ScriptedBot("bbbbbb", ["PAUSED"], resting_orders=2),
            ScriptedBot("cccccc", ["STOPPED"], resting_orders=0),
            ScriptedBot("dddddd", ["DRAFT"]),
        ]
    )
    caplog.set_level(logging.INFO, logger=_LOGGER)

    LeaveOrdersResting(world).apply(StopLedger(), threading.Event())

    # The only thing it asked the bots was to read; nothing was stopped.
    assert world.stops() == []
    text = "\n".join(_infos(caplog))
    assert "aaaaaa (RUNNING) 4 orders resting" in text
    assert "bbbbbb (PAUSED) 2 orders resting" in text
    assert "cccccc" not in text and "dddddd" not in text  # at rest: nothing to leave
    assert "leave-orders" in text
    assert "6 orders" in text  # the total a person reads first


def test_leave_orders_resting_with_no_active_bot_says_there_is_nothing_to_leave(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=_LOGGER)

    LeaveOrdersResting(BotsWorld([ScriptedBot("cccccc", ["STOPPED"])])).apply(
        StopLedger(), threading.Event()
    )

    assert any("no bot is active" in m for m in _infos(caplog))


def test_a_bot_whose_orders_are_not_known_is_left_with_the_count_unknown(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=_LOGGER)

    LeaveOrdersResting(BotsWorld([ScriptedBot("aaaaaa", ["RECOVERING"])])).apply(
        StopLedger(), threading.Event()
    )

    assert any(
        "aaaaaa (RECOVERING) orders resting: unknown" in m for m in _infos(caplog)
    )


def test_stop_bots_first_dispatches_the_existing_stop_for_each_active_bot_only() -> (
    None
):
    world = BotsWorld(
        [
            ScriptedBot(
                "aaaaaa",
                ["RUNNING", "STOPPING", "STOPPED"],
                3,
                after_stop=["STOPPING", "STOPPED"],
            ),
            ScriptedBot("bbbbbb", ["HALTED"], 1, after_stop=["STOPPING", "STOPPED"]),
            ScriptedBot("cccccc", ["STOPPED"]),
            ScriptedBot("dddddd", ["DRAFT"]),
        ]
    )
    ledger = StopLedger()

    StopBotsFirst(world, poll_s=0).apply(ledger, threading.Event())

    assert world.stops() == ["aaaaaa", "bbbbbb"]
    assert ledger.left() == ()
    assert set(ledger.finished()) == {"aaaaaa", "bbbbbb"}


def test_stop_bots_first_leaves_what_did_not_stop_in_the_ledger() -> None:
    """The bot never reaches STOPPED; the host's timeout fires (`give_up`)."""
    give_up = threading.Event()
    world = BotsWorld(
        [ScriptedBot("aaaaaa", ["STOPPING"], 3, after_stop=["STOPPING"])],
        on_read=lambda reads: give_up.set() if reads >= 3 else None,
    )
    ledger = StopLedger()

    StopBotsFirst(world, poll_s=0).apply(ledger, give_up)

    (left,) = ledger.left()
    assert (left.bot_id, left.state, left.resting_orders) == ("aaaaaa", "STOPPING", 3)
    # The WARNING that names it is the host's, which owns the timeout
    # (`test_run_host.py::test_a_policy_that_does_not_finish_in_time_is_given_up_on_and_named`).


def test_a_refused_stop_is_logged_at_warning_and_the_bot_is_left(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = BotsWorld(
        [
            ScriptedBot(
                "aaaaaa", ["RUNNING"], 2, stop_refusal=BotRefusal.INVALID_TRANSITION
            ),
            ScriptedBot("bbbbbb", ["RUNNING", "STOPPED"], 1, after_stop=["STOPPED"]),
        ]
    )
    ledger = StopLedger()
    caplog.set_level(logging.INFO, logger=_LOGGER)

    StopBotsFirst(world, poll_s=0).apply(ledger, threading.Event())

    (left,) = ledger.left()
    assert left.bot_id == "aaaaaa"
    assert "refused" in left.note
    assert any("aaaaaa" in m and "refused" in m for m in _warnings(caplog))
    assert "bbbbbb" in ledger.finished()


def test_a_bot_already_stopping_is_waited_for_not_asked_again() -> None:
    world = BotsWorld([ScriptedBot("aaaaaa", ["STOPPING", "STOPPING", "STOPPED"], 1)])
    ledger = StopLedger()

    StopBotsFirst(world, poll_s=0).apply(ledger, threading.Event())

    assert world.stops() == []
    assert ledger.left() == ()
