"""`EPIC-039I` - what only a NEUTRAL Futures grid does, on the fake exchange.

@details The shared journeys (`test_every_direction_passes_the_shared_journeys_...`) run NEUTRAL
as one row. These are its own: it opens nothing and lays entries on both sides, its position
crosses zero as the price crosses its start, and out of range it is net short at its maximum above
the range and net long at its maximum below it, holding or closing as the definition says.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.bot_exchange_terms import (
    exchange_terms_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    LevelSizing,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_position_model import (
    model_position_along,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)

from .futures_bots_world import ORDER_QUANTITY, booted_futures_bots
from .futures_direction_scenarios import NEUTRAL
from .futures_fake_exchange import FUTURES, SYMBOL
from .grid_fake_exchange import FakeExchange
from .test_a_futures_grid_halts_and_recovers_on_the_fake_exchange import _started

S = BotLifecycleState
D = Decimal
_Q = ORDER_QUANTITY


def test_a_neutral_bot_opens_nothing_and_lays_entries_on_both_sides(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, NEUTRAL.config)

        assert app.bot(bot_id).state is S.RUNNING
        assert app.position() == 0, "no opening trade"
        assert app.runtime(bot_id).inventory == 0
        resting = sorted(app.resting().values())
        assert {side for side, _price, _reduce in resting} == {"BUY", "SELL"}
        assert not any(reduce for _side, _price, reduce in resting), "none only exits"
        assert [price for side, price, _ in resting if side == "BUY"] == [
            D(62000),
            D(63000),
        ]
        assert [price for side, price, _ in resting if side == "SELL"] == [
            D(65000),
            D(66000),
        ]


def test_a_neutral_path_crossing_the_start_price_repeatedly_stays_consistent_and_ends_flat(
    futures: FakeExchange,
) -> None:
    """Each price crosses one rung: the position goes long, back through zero, short, back. After
    every price the exchange, the bot's own count and the position function agree, no counter is
    rejected, and the stop ends flat."""
    path = [D(62900), D(64100), D(65100), D(63900)] * 3 + [D(62900), D(61900), D(63100)]
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, NEUTRAL.config)
        container = app.engine.context.container
        ports = container.resolve(IVenueTradingPorts).get(FUTURES)
        terms = exchange_terms_for(
            ports.order_entry_terms, SYMBOL, container.resolve(OwnerBudgetCaps)
        )
        planned = plan(
            GridParams.from_config(NEUTRAL.config),
            terms,
            D(64000),
            LevelSizing.EQUAL_QUANTITY,
        )
        signs: set[int] = set()
        cycles_of_the_oscillation = 0

        for step, price in enumerate(path, start=1):
            app.move_price(price)
            modelled = model_position_along(planned, path[:step])

            runtime = app.runtime(bot_id)
            assert app.bot(bot_id).state is S.RUNNING, (
                price,
                runtime.reason,
                runtime.reason_detail,
            )
            assert app.position() == modelled.position, f"exchange at {price}"
            assert runtime.inventory == modelled.position, f"bot count at {price}"
            assert {o.client_order_id for o in runtime.open_orders} == set(
                app.resting()
            )
            signs.add((modelled.position > 0) - (modelled.position < 0))
            if step == 12:
                cycles_of_the_oscillation = runtime.completed_cycles
                # Three times a buy then its sell, a sell then its buy back: six cycles of one
                # rung (1,000) at the ladder's quantity, less commissions.
                assert runtime.realised_profit <= 6 * 1000 * _Q
                assert runtime.realised_profit > 5 * 1000 * _Q
        assert signs == {-1, 0, 1}, "the path really crossed zero both ways"
        assert cycles_of_the_oscillation == 6

        app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, ExposureHandling.CLOSE_AT_MARKET)
        )
        app.deliver()

        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0
        assert app.resting() == {}


def test_above_the_range_a_neutral_bot_is_net_short_at_its_maximum_and_holds(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, NEUTRAL.config)

        app.move_price(65100)  # one rung a price: the fake's delivery is not re-entrant
        app.move_price(66100)  # both SELL entries have filled
        app.ticker.fire()
        app.deliver()

        assert app.position() == -2 * _Q
        assert app.bot(bot_id).state is S.RUNNING, "out of range holds by default"


def test_below_the_range_a_neutral_bot_is_net_long_at_its_maximum_and_holds(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, NEUTRAL.config)

        app.move_price(62900)
        app.move_price(61900)  # both BUY entries have filled
        app.ticker.fire()
        app.deliver()

        assert app.position() == 2 * _Q
        assert app.bot(bot_id).state is S.RUNNING


def test_out_of_range_the_bot_closes_whichever_way_it_stands_when_asked_to(
    futures: FakeExchange,
) -> None:
    config = {**NEUTRAL.config, "take_profit": "price:80000", "on_range_exit": "close"}
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, config)

        app.move_price(65100)
        app.move_price(66100)
        assert app.position() == -2 * _Q
        app.ticker.fire()
        app.deliver()

        assert app.runtime(bot_id).reason is GridReason.RANGE_EXIT
        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0
        assert app.resting() == {}


def test_the_take_profit_closes_a_real_short_whole_and_stops_flat(
    futures: FakeExchange,
) -> None:
    """The short leg's loss exit (decision of 039B): the mark through the take profit closes the
    position the bot holds, reduce-only, and the bot ends flat with nothing resting."""
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, NEUTRAL.config)  # take profit at 66,500
        app.move_price(65100)
        app.move_price(66100)
        assert app.position() == -2 * _Q

        app.move_price(66600)  # the mark through the take profit
        app.ticker.fire()
        app.deliver()

        assert app.runtime(bot_id).reason is GridReason.TAKE_PROFIT
        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0
        assert app.resting() == {}
        assert app.runtime(bot_id).inventory == 0


def test_the_stop_loss_closes_a_real_long_whole_and_stops_flat(
    futures: FakeExchange,
) -> None:
    """The long leg's loss exit: the mark through the stop loss closes the position held."""
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, {**NEUTRAL.config, "stop_loss": "price:61500"})
        app.move_price(62900)
        app.move_price(61900)
        assert app.position() == 2 * _Q

        app.move_price(61400)  # the mark through the stop loss
        app.ticker.fire()
        app.deliver()

        assert app.runtime(bot_id).reason is GridReason.STOP_LOSS
        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0
        assert app.resting() == {}
        assert app.runtime(bot_id).inventory == 0
