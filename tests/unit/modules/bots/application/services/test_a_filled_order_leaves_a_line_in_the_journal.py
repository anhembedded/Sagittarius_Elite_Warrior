"""`BUG-264` - every order of the ladder that fills whole leaves one INFO line saying what it did
to the books, so a cycle count can be audited from the journal.

@details The owner's journal showed a fill only as a position divergence followed by the counter
order; a Cycles figure one short of the fills could not be traced. The same executor and simulated
venue as `test_grid_tells_the_app_about_a_filled_order.py`.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    GridWorld,
    grid_world,
)

_TAG = "[order-filled]"


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    return world


def _lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if _TAG in r.getMessage()]


def test_an_entry_fill_says_it_closed_no_cycle(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = _running()
    order_id = world.open_ids_by_price()[Decimal(110)]

    with caplog.at_level(logging.INFO, logger="App"):
        world.fill(Decimal(110), "2.272")

    [line] = _lines(caplog)
    assert line.startswith(
        f"Bot {BOT}: {order_id} L1 BUY 2.272 @ 110 filled whole; 0 cycle(s)"
    )
    assert "this fill closed no cycle" in line


def test_the_completing_fill_says_the_cycle_it_closed_and_the_profit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = _running()
    world.fill(Decimal(110), "2.272")
    order_id = world.open_ids_by_price()[Decimal(120)]

    with caplog.at_level(logging.INFO, logger="App"):
        world.fill(Decimal(120), "2.272")

    [line] = _lines(caplog)
    assert (
        f"{order_id} L2 SELL 2.272 @ 120 filled whole; 1 cycle(s), grid profit 22.720"
        in line
    )
    assert "this fill closed a cycle: +22.720" in line
