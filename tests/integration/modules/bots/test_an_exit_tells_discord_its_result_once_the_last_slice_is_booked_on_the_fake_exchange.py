"""`BOT-190` (`PRO-015` §2.3) - the owner hears what an exit realized, once its position is closed.

@details The composed app over the fake Binance server with alerting live, as the `BOT-189` journeys
(`test_a_bot_tells_discord_about_every_fill_cycle_and_exit_on_the_fake_exchange.py`, whose fixtures
it reuses). The bot becomes STOPPED before the closing market slices fill, so the message waits for
the bot's own event, published after the slice that leaves the run holding dust is booked, and
carries the run's books at that moment.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    plain_money,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_pnl import pnl_summary

from .grid_fake_exchange import FakeExchange
from .test_a_bot_tells_discord_about_every_fill_cycle_and_exit_on_the_fake_exchange import (
    _settled,
    _started,
    _tick,
    _told,
)

S = BotLifecycleState


@pytest.fixture(autouse=True)
def _data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))


def test_a_stop_loss_tells_the_result_the_books_hold_once_its_last_slice_is_booked(
    exchange: FakeExchange,
) -> None:
    """The exit sells in several slices, each booked after the bot is STOPPED; the one message
    carries the run's books after the last of them, the exit's fee included, and not the
    mark-to-market the status report held when the bot became STOPPED."""
    with _told(exchange) as (app, transport):
        bot_id = _started(app)
        app.move_price(
            48000
        )  # both ladder buys fill: the bot holds more than one slice's worth
        _settled(app, transport)
        at_stopped: list[Decimal | None] = []

        def note_the_total_at_stopped(event: BotChangedEvent) -> None:
            if event.bot_id == bot_id and app.bot(bot_id).state is S.STOPPED:
                at_stopped.append(pnl_summary(app.runtime(bot_id), None).total)

        app.engine.event_bus.on(BotChangedEvent, note_the_total_at_stopped)

        _tick(app, 39_000.0)
        messages = _settled(app, transport)

        assert app.bot(bot_id).state is S.STOPPED
        final = pnl_summary(app.runtime(bot_id), None).total
    [closed] = [m for m in messages if "Position closed: grid" in m]
    assert final is not None and at_stopped[0] is not None
    assert final != at_stopped[0], "the exit's fill must move the total"
    assert f"The run's result: {plain_money(final)}" in closed
    assert plain_money(at_stopped[0]) not in closed
    assert "The stop loss closed the position" in closed
    assert "INFO" in closed


@pytest.mark.parametrize(
    "handling", [ExposureHandling.CLOSE_AT_MARKET, ExposureHandling.KEEP]
)
def test_a_stop_the_owner_asked_for_sends_no_result_whether_it_sells_or_keeps(
    exchange: FakeExchange, handling: ExposureHandling
) -> None:
    with _told(exchange) as (app, transport):
        bot_id = _started(app)
        app.move_price(48000)
        _settled(app, transport)

        app.engine.dispatch(StopBotCommand, StopBotCommand(bot_id, handling))
        app.deliver()
        messages = _settled(app, transport)

        assert app.bot(bot_id).state is S.STOPPED
    assert not [m for m in messages if "Position closed" in m]
