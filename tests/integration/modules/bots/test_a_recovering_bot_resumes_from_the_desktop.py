"""`BUG-204` — a RECOVERING bot has a desktop way out, and a fill that landed meanwhile is booked once.

@details The owner's real-money bot was RECOVERING after a restart, the order
session closed, and its level-2 buy filled on the exchange. Nothing listened
(the user-data stream starts only with the session) and the only way to open
the session was to start something else or place a manual order; the bot's own
Resume had no cell in the lifecycle table. This drives the journey the Bots
screen offers: the app restarts with the session closed, the price falls
through a buy, the owner presses Resume, and the same reconcile the
`TradingSwitchChangedEvent` runs books the fill, lays its sell once and puts
the bot back to RUNNING. Substitutions are `grid_fake_exchange.booted`'s; the
one websocket call (`SpotUserDataStream.start`) is stubbed as in
`test_a_bot_starts_from_a_closed_session_and_opens_it_itself`.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)

from .grid_fake_exchange import (
    GRID,
    SPOT,
    SYMBOL,
    FakeExchange,
    booted,
    ladder,
    resting,
    sides_by_price,
)

S = BotLifecycleState


def test_resume_opens_the_session_and_books_a_fill_that_landed_while_recovering(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as first:
        created = first.engine.dispatch(
            CreateBotCommand, CreateBotCommand("grid", "grid", SPOT, SYMBOL, GRID)
        )
        assert isinstance(created, BotCommandResult)
        assert created.bot_id is not None
        bot_id = created.bot_id
        started = first.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))
        assert isinstance(started, BotCommandResult)
        assert started.accepted, started.message
        bought_before = first.runtime(bot_id).inventory

    with booted(exchange, open_session=False) as second:
        starts: list[str] = []
        second.stream.start = lambda: starts.append("start")  # type: ignore[method-assign]
        assert second.bot(bot_id).state is S.RECOVERING
        assert second.scope.session_state.enabled is False

        # After the restart the 48,800 buy fills; no stream is open to hear it.
        exchange.urls.spot_account.set_last_price(SYMBOL, Decimal(48700))
        exchange.urls.spot_account.drain_user_data_events()
        assert second.runtime(bot_id).inventory == bought_before

        resumed = second.engine.dispatch(ResumeBotCommand, ResumeBotCommand(bot_id))

        assert isinstance(resumed, BotCommandResult)
        assert resumed.accepted, resumed.message
        assert second.scope.session_state.enabled is True
        assert starts == ["start"]
        runtime = second.runtime(bot_id)
        assert second.bot(bot_id).state is S.RUNNING
        assert resting(second.urls) == ladder(runtime)
        prices = [price for _side, price in resting(second.urls).values()]
        assert len(prices) == len(set(prices))
        assert sides_by_price(runtime)[Decimal(49600)] == "SELL"
        assert Decimal(48800) not in sides_by_price(runtime)
        assert runtime.inventory > bought_before
