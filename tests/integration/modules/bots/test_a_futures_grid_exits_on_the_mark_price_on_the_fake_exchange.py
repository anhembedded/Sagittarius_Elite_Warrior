"""`EPIC-039H` - a Futures Grid's take profit is judged on the mark price, on the fake exchange.

@details The composed app over the Futures testnet fake (`futures_bots_world`). The last price the
kline stream shows going through the take profit does not stop the bot; the exchange's mark price
going through it does, on the next beat of the price watch, and the bot ends flat with nothing
resting (the stop closes at market, reduce-only).
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

from .futures_bots_world import GRID, booted_futures_bots
from .grid_fake_exchange import FakeExchange
from .test_a_futures_grid_halts_and_recovers_on_the_fake_exchange import (
    _publish_tick,
    _started,
)

S = BotLifecycleState
_TAKE_PROFIT = {**GRID, "take_profit": "price:66500"}


def test_a_last_price_through_the_take_profit_does_not_stop_a_futures_bot(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, _TAKE_PROFIT)

        _publish_tick(app, 71000.0)
        app.ticker.fire()
        app.deliver()

        assert app.bot(bot_id).state is S.RUNNING
        assert app.position() > 0


def test_a_mark_price_through_the_take_profit_closes_the_position_and_stops_the_bot(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, _TAKE_PROFIT)

        # The market moves through the take profit while the exchange has not filled the 66,000
        # sell yet: the bot still holds its opening, which the stop must close.
        futures.urls.futures_book.faults.hold_fills = True
        app.move_price(Decimal(66600))  # the fake's one price is the mark too
        assert app.position() > 0
        app.ticker.fire()
        app.deliver()

        assert app.runtime(bot_id).reason is GridReason.TAKE_PROFIT
        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0
        assert app.resting() == {}
