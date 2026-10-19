"""`BUG-228`, `BUG-229` - a Futures bot's stop that closes its position, while the exchange's open-orders
list still shows the orders the stop just cancelled, on the fake exchange.

@details The owner's desktop: a BTC grid and an ETH grid on one Futures venue and account. The
BTC bot is stopped with the close-position option while the venue's open-orders list lags (a
cancel the list has not caught up with, `MatchFaults.stale_open_orders`). The stop registers the
bot's budget again, which adopts what the list shows as open orders, so the close slices meet an
owner budget that looks full. A close only reduces the position: it must not be refused for the
bot's own orders, and a cancel of an order the exchange no longer knows (`-2011`) is gone, not a
fault. The ETH bot, beside it, is untouched.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .crowd_bots_world import ETH_GRID, create_bot, start_bot
from .grid_fake_exchange import FakeExchange
from .two_venues_bots_world import FUTURES, BootedTwoVenues, booted_two_venues

S = BotLifecycleState
BTC = "BTCUSDT"
ETH = "ETHUSDT"


def _two_running(app: BootedTwoVenues) -> tuple[str, str]:
    btc = create_bot(app, FUTURES, BTC)
    eth = create_bot(app, FUTURES, ETH, params=ETH_GRID)
    for bot_id in (btc, eth):
        started = start_bot(app, bot_id)
        assert started.accepted, started.message
    return btc, eth


def _stop_and_close(app: BootedTwoVenues, bot_id: str) -> None:
    stopped = app.engine.dispatch(
        StopBotCommand, StopBotCommand(bot_id, ExposureHandling.CLOSE_AT_MARKET)
    )
    assert isinstance(stopped, BotCommandResult) and stopped.accepted


def _btc_position(app: BootedTwoVenues) -> Decimal:
    return sum(
        (p.position_amt for p in app.client(FUTURES).get_positions(BTC)), Decimal(0)
    )


def test_a_close_is_not_refused_for_orders_the_list_still_shows_and_the_stop_waits_for_the_list(
    both_venues: FakeExchange,
) -> None:
    faults = both_venues.urls.futures_book.faults
    with booted_two_venues(both_venues) as app:
        btc, eth = _two_running(app)
        eth_orders = app.resting(FUTURES, ETH)
        states: list[S] = []
        app.engine.context.container.resolve(IEventBus).on(
            BotChangedEvent,
            lambda event: (
                states.append(app.bot(event.bot_id).state)
                if event.bot_id == btc
                else None
            ),
        )
        faults.stale_open_orders = True

        _stop_and_close(app, btc)

        # Neither the close nor the cancels failed on the way: the bot never halted.
        assert S.HALTED not in states and S.ERROR not in states, states
        runtime = app.runtime(btc)
        assert app.bot(btc).state is S.STOPPING, (runtime.reason, runtime.reason_detail)
        assert "unsold" not in runtime.reason_detail
        assert _btc_position(app) == 0
        faults.stale_open_orders = False
        assert app.resting(FUTURES, BTC) == set()

        _stop_and_close(app, btc)

        assert app.bot(btc).state is S.STOPPED
        assert app.resting(FUTURES, ETH) == eth_orders
        assert {tag_of(o) for o in eth_orders} == {eth}
        assert app.bot(eth).state is S.RUNNING


def test_a_cancel_of_an_order_the_exchange_no_longer_knows_leaves_the_stop_waiting_not_in_error(
    both_venues: FakeExchange,
) -> None:
    faults = both_venues.urls.futures_book.faults
    with booted_two_venues(both_venues) as app:
        btc, _eth = _two_running(app)
        faults.stale_open_orders = True
        _stop_and_close(app, btc)

        _stop_and_close(app, btc)  # the list still shows what the first stop cancelled

        runtime = app.runtime(btc)
        assert app.bot(btc).state is S.STOPPING, (runtime.reason, runtime.reason_detail)
        faults.stale_open_orders = False
        _stop_and_close(app, btc)
        assert app.bot(btc).state is S.STOPPED
