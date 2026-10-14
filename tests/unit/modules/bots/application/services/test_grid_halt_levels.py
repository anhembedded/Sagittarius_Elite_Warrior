"""`BUG-209` — a Grid that halts for a refusal of ours reaches WARNING, with the reason.

A pre-send refusal (the safety gate, the limits, the session lease, the minimum notional)
is trading's answer, not an exception, and the bot turns it into `halt` or `start_refused`.
Those lines were INFO, so the owner's grep for WARNING, ERROR and CRITICAL found nothing
though the bot had stopped. The transition now carries the level; these tests drive the
refusal from the exchange side of the simulated venue, through the real executor.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderNotionalRejection,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    grid_world,
)

S = BotLifecycleState
LOGGER = "App.Bots.GridExecutor"


def _at_or_above_warning(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_a_start_refused_by_the_min_notional_is_a_warning_naming_the_gate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = grid_world()
    world.book.refuse_next = [ExecuteOrderNotionalRejection.MIN_NOTIONAL]

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        world.executor.start()

    assert world.state() is S.HALTED
    (record,) = _at_or_above_warning(caplog)
    assert record.levelno == logging.WARNING
    assert "STARTING -> HALTED" in record.getMessage()
    assert "min_notional" in record.getMessage().lower()


def test_a_running_bot_halted_by_the_session_lease_is_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    world.book.refuse_next = [ExecuteOrderSafetyGate.SYMBOL_LEASED]
    caplog.clear()

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        world.fill(Decimal(110), "2.272")

    assert world.state() is S.HALTED
    warnings = [
        r for r in _at_or_above_warning(caplog) if "-> HALTED" in r.getMessage()
    ]
    assert len(warnings) == 1, "one halt, one WARNING"
    assert "symbol_leased" in warnings[0].getMessage().lower()


def test_a_bot_faulted_by_a_failing_step_is_an_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = grid_world()
    world.executor.start()
    caplog.clear()
    world.book.raise_next = [ConnectionError("read timed out")]

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        world.fill(Decimal(110), "2.272")

    assert world.state() is S.ERROR
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any("-> ERROR" in r.getMessage() for r in errors)
