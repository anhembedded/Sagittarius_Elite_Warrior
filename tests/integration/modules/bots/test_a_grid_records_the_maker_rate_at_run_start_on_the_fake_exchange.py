"""`BOT-194` - a run's start records the account's maker rate, and both consumers show it.

@details The composed app over the fake Futures exchange (maker 0.02 %): the start sequence writes
the rate it read into the saved runtime; then the two consumers read the saved record with no
exchange call. `bot show` is run through the status query handler the app binds (`bot_show_report`
over `GetBotStatusReportQuery`) and the Bots tab through its `detail_for`, and each shows the net
after fees from that rate, worded as the rate recorded at run start.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_progress_reader import (
    bot_progress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_status_reports import (
    bot_show_report,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusReport,
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    GridLadder,
    grid_ladder_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_detail import (
    DetailInputs,
    detail_for,
)

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


def test_bot_show_and_the_bots_tab_both_show_the_recorded_rate(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, NEUTRAL.config)
        dispatcher = app.engine.context.container.resolve(ICommandDispatcher)

        status = dispatcher.dispatch(
            GetBotStatusReportQuery, GetBotStatusReportQuery(bot_id)
        )
        assert isinstance(status, BotStatusReport)
        [entry] = status.bots
        shown = " ".join(
            cell.text
            for section in bot_show_report(status).layout
            for row in section.rows
            for cell in row.cells
        )
        stored = app.store.load(BotId(bot_id))
        snapshot = BotSnapshot.of(stored.bot, bot_progress(stored))
        tab = detail_for(DetailInputs(snapshot, None, None, _NOW)).ladder

        assert isinstance(entry.ladder, GridLadder)
        assert entry.ladder.summary.maker_fee == _FAKE_MAKER_RATE
        assert (
            "after the 0.02% maker fee on both legs (rate recorded at run start)"
            in shown
        )
        assert isinstance(tab, GridLadder)
        assert tab.summary.maker_fee == _FAKE_MAKER_RATE
