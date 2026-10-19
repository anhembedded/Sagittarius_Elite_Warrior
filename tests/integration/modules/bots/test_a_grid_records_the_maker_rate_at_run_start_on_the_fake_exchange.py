"""`BOT-194` - a run's start records the account's maker rate, and the readers use it.

@details The composed app over the fake Futures exchange (maker 0.02 %): the start sequence writes
the rate it read into the saved runtime, and the ladder both consumers build from the saved record
(the Bots tab's `detail_for` and `bot show`'s status handler call `grid_ladder_of`) shows the net
after fees from it with no exchange call. A resume keeps the recorded rate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_progress_reader import (
    bot_progress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    GridLadder,
    grid_ladder_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId

from .futures_bots_world import booted_futures_bots
from .futures_direction_scenarios import NEUTRAL
from .futures_fake_exchange import FakeExchange
from .test_a_futures_grid_halts_and_recovers_on_the_fake_exchange import _started

_FAKE_MAKER_RATE = Decimal("0.0002")
_NOW = datetime(2026, 10, 19, tzinfo=UTC)


def test_the_start_records_the_rate_and_the_ladder_shows_the_net_from_it(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, NEUTRAL.config)

        stored = app.store.load(BotId(bot_id))
        snapshot = BotSnapshot.of(stored.bot, bot_progress(stored))
        ladder = grid_ladder_of(snapshot, _NOW)

        assert app.runtime(bot_id).maker_fee == _FAKE_MAKER_RATE
        assert isinstance(ladder, GridLadder)
        assert ladder.summary.maker_fee == _FAKE_MAKER_RATE
        assert all(row.net_fraction is not None for row in ladder.rows)
        assert all(
            row.net_fraction == row.step_fraction - 2 * _FAKE_MAKER_RATE
            for row in ladder.rows
        )
