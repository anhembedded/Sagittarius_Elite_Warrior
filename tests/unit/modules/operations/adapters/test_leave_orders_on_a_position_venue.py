"""`EPIC-038M` (decision O12) - the host's default stop on a Futures bot: leave what a stop covers, close the rest."""

from __future__ import annotations

import logging
import threading

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    StopCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.leave_orders_resting import (
    LeaveOrdersResting,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_policy import (
    StopLedger,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.stop_policy_world import (
    BotsWorld,
    ScriptedBot,
)

_LOGGER = "App.Operations.StopPolicy"
_FUTURES = "futures_mainnet"
_TIMEOUT_S = 10.0
S = StopCoverage


def _futures(
    bot_id: str,
    coverage: StopCoverage,
    words: str = "",
    after_stop: tuple[str, ...] = ("STOPPING", "STOPPED"),
    stop_refusal: BotRefusal | None = None,
) -> ScriptedBot:
    return ScriptedBot(
        bot_id,
        ["RUNNING"],
        resting_orders=4,
        stop_refusal=stop_refusal,
        after_stop=list(after_stop),
        venue=_FUTURES,
        coverage=coverage,
        coverage_words=words,
    )


def _policy(world: BotsWorld, now: list[float] | None = None) -> LeaveOrdersResting:
    clock = (lambda: now[0]) if now is not None else (lambda: 0.0)
    return LeaveOrdersResting(world, _TIMEOUT_S, clock=clock, poll_s=0)


def _text(caplog: pytest.LogCaptureFixture, level: int) -> str:
    return "\n".join(r.getMessage() for r in caplog.records if r.levelno == level)


def test_a_futures_bot_whose_stop_covers_its_position_is_left_as_it_is(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = BotsWorld([_futures("aaaaaa", S.COVERED, "its protective stop stands")])
    caplog.set_level(logging.INFO, logger=_LOGGER)
    ledger = StopLedger()

    _policy(world).apply(ledger, threading.Event())

    assert world.stops() == []
    assert ledger.left() == () and ledger.finished() == ()
    infos = _text(caplog, logging.INFO)
    assert "aaaaaa (RUNNING) 4 orders resting" in infos
    assert "its stop covers its position" in infos
    assert _text(caplog, logging.WARNING) == ""


@pytest.mark.parametrize(
    ("coverage", "words"),
    [
        (S.UNCOVERED, "no protective stop stands over it"),
        (S.UNCOVERED, "its protective stop stands but does not cover the position"),
        (S.UNREAD, "whether its protective stop stands could not be read"),
    ],
)
def test_a_futures_bot_whose_stop_is_missing_wrong_or_unread_is_closed_before_exit(
    coverage: StopCoverage, words: str, caplog: pytest.LogCaptureFixture
) -> None:
    world = BotsWorld([_futures("aaaaaa", coverage, words)])
    caplog.set_level(logging.INFO, logger=_LOGGER)
    ledger = StopLedger()

    _policy(world).apply(ledger, threading.Event())

    # The Stop the Bots tab's "Close the position at market" dispatches, not a keep.
    assert world.closes() == ["aaaaaa"]
    assert world.stops() == ["aaaaaa"]
    assert ledger.finished() == ("aaaaaa",) and ledger.left() == ()
    warnings = _text(caplog, logging.WARNING)
    assert "aaaaaa" in warnings and words in warnings and "closing" in warnings


def test_a_bot_that_closes_is_named_in_the_ledger_until_it_is_stopped() -> None:
    give_up = threading.Event()
    world = BotsWorld(
        [
            _futures(
                "aaaaaa",
                S.UNCOVERED,
                "no protective stop stands over it",
                after_stop=("STOPPING",),  # never reaches STOPPED
            )
        ],
        on_read=lambda reads: give_up.set() if reads > 3 else None,
    )
    ledger = StopLedger()

    _policy(world).apply(ledger, give_up)

    (left,) = ledger.left()
    assert left.bot_id == "aaaaaa" and left.state == "STOPPING"
    assert "no protective stop stands over it" in left.note
    assert ledger.finished() == ()


def test_only_the_bots_without_a_covering_stop_are_closed() -> None:
    world = BotsWorld(
        [
            _futures("aaaaaa", S.COVERED),
            _futures("bbbbbb", S.UNCOVERED, "no protective stop stands over it"),
            ScriptedBot("cccccc", ["RUNNING"], resting_orders=2),
            _futures("dddddd", S.NOTHING_EXPOSED),
        ]
    )

    _policy(world).apply(StopLedger(), threading.Event())

    assert world.closes() == ["bbbbbb"]
    assert world.stops() == ["bbbbbb"]


def test_a_spot_bot_is_left_with_no_stop_asked() -> None:
    world = BotsWorld([ScriptedBot("aaaaaa", ["RUNNING"], resting_orders=3)])

    _policy(world).apply(StopLedger(), threading.Event())

    assert world.stops() == []


def test_a_bot_already_stopping_is_waited_for_and_not_read_or_asked_again() -> None:
    world = BotsWorld(
        [
            ScriptedBot(
                "aaaaaa",
                ["STOPPING", "STOPPED"],
                venue=_FUTURES,
                coverage=S.UNCOVERED,
            )
        ]
    )
    ledger = StopLedger()

    _policy(world).apply(ledger, threading.Event())

    assert world.stops() == [] and world.coverage_asked() == []
    assert ledger.finished() == ("aaaaaa",)


def test_a_close_the_lifecycle_refuses_is_a_warning_and_the_bot_stays_in_the_ledger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = BotsWorld(
        [
            _futures(
                "aaaaaa",
                S.UNCOVERED,
                "no protective stop stands over it",
                stop_refusal=BotRefusal.INVALID_TRANSITION,
            )
        ]
    )
    caplog.set_level(logging.INFO, logger=_LOGGER)
    ledger = StopLedger()

    _policy(world).apply(ledger, threading.Event())

    (left,) = ledger.left()
    assert left.bot_id == "aaaaaa" and "the stop was refused" in left.note
    assert "aaaaaa" in _text(caplog, logging.WARNING)


def test_when_the_read_budget_runs_out_the_rest_are_closed_unread_and_the_log_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The deadline cannot be met by reading every bot: the safe side is closing (decision O12)."""
    now = [0.0]
    world = BotsWorld(
        [
            _futures("aaaaaa", S.COVERED),
            _futures("bbbbbb", S.COVERED),
            _futures("cccccc", S.COVERED),
        ],
        on_coverage=lambda _bot: now.__setitem__(0, now[0] + _TIMEOUT_S / 2),
    )
    caplog.set_level(logging.INFO, logger=_LOGGER)

    _policy(world, now).apply(StopLedger(), threading.Event())

    # The first read took the whole read budget; the other two were never read.
    assert world.coverage_asked() == ["aaaaaa"]
    assert world.closes() == ["bbbbbb", "cccccc"]
    warnings = _text(caplog, logging.WARNING)
    assert "bbbbbb" in warnings and "cccccc" in warnings
    assert "deadline" in warnings and "aaaaaa" not in warnings


def test_a_stop_that_never_finishes_ends_when_the_host_gives_up() -> None:
    give_up = threading.Event()
    world = BotsWorld(
        [_futures("aaaaaa", S.UNREAD, after_stop=("STOPPING",))],
        on_read=lambda reads: give_up.set() if reads > 2 else None,
    )
    ledger = StopLedger()

    _policy(world).apply(ledger, give_up)

    assert [b.bot_id for b in ledger.left()] == ["aaaaaa"]


def test_a_bot_not_looked_at_because_the_host_stopped_waiting_stays_in_the_ledger() -> (
    None
):
    world = BotsWorld(
        [_futures("aaaaaa", S.UNCOVERED, "no protective stop stands over it")]
    )
    give_up = threading.Event()
    give_up.set()
    ledger = StopLedger()

    _policy(world).apply(ledger, give_up)

    assert world.stops() == [] and world.coverage_asked() == []
    (left,) = ledger.left()
    assert left.bot_id == "aaaaaa" and "host stopped waiting" in left.note
