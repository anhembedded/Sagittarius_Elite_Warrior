"""`BUG-196` — a start records the base the bot's earlier runs left.

@details The real executor over the simulated venue; the session is
`FakeTradingSession` (the port's fake), told what the exchange's history says.
The start never refuses for it: a venue that does not answer is a log line.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    decode_runtime,
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsInventory,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    RUN_STARTED,
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.grid_runtime_builders import (
    started_ladder,
)

_SEEN = datetime(2026, 10, 9, tzinfo=UTC)


def test_a_start_records_what_earlier_runs_left_and_asks_for_the_right_owner() -> None:
    world = grid_world()
    world.session.earlier_runs_answers(
        EarlierRunsInventory(Decimal("0.0083"), Decimal("20.5"), _SEEN)
    )

    world.executor.start()

    runtime = world.runtime()
    assert runtime.earlier_runs_base == Decimal("0.0083")
    assert runtime.earlier_runs_cost == Decimal("20.5")
    (request,) = world.session.earlier_runs_requests
    assert request.tag == BOT
    assert request.until == RUN_STARTED
    assert world.state() is BotLifecycleState.RUNNING


def test_a_venue_that_does_not_answer_does_not_stop_the_start(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = grid_world()
    world.session.earlier_runs_answers(EarlierRunsInventory(unavailable="down"))

    with caplog.at_level(logging.WARNING, logger="App.Bots.GridExecutor"):
        world.executor.start()

    assert world.state() is BotLifecycleState.RUNNING
    assert world.runtime().earlier_runs_base == 0
    assert "[earlier-runs]" in caplog.text


def test_the_figure_survives_the_store_and_an_older_file_reads_as_none() -> None:
    runtime = GridRuntime(
        started_ladder().levels,
        earlier_runs_base=Decimal("0.0083"),
        earlier_runs_cost=Decimal("20.5"),
    )
    written = encode_runtime(runtime)

    assert decode_runtime(written).earlier_runs_base == Decimal("0.0083")
    del written["earlier_runs_base"]
    del written["earlier_runs_cost"]
    assert decode_runtime(written).earlier_runs_base == 0
