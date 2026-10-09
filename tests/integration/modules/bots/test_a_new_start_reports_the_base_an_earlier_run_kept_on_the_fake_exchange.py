"""`BUG-196` — a new Start tells the owner about the base a previous run kept.

@details The composed app over the fake Binance server. A run counts only its
own orders (ADR D6), so after Start, Stop (keep the base) and Start again the
account holds two openings while the second run's book holds one. The base the
first run kept must not stay silently nobody's: the second run records it, from
the exchange's history and capped by what the account still holds, and the bot's
figures show it. It is never traded and never a reason to refuse the Start.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)

from .grid_fake_exchange import FakeExchange, booted
from .test_a_start_with_the_user_stream_down_on_the_fake_exchange import _held, _start


def _stop_keeping_the_base(app, bot_id: str) -> None:
    stopped = app.engine.dispatch(
        StopBotCommand, StopBotCommand(bot_id, BaseHandling.KEEP)
    )
    assert isinstance(stopped, BotCommandResult)
    assert stopped.accepted, stopped.message
    assert app.bot(bot_id).state is BotLifecycleState.STOPPED


def _start_again(app, bot_id: str) -> None:
    started = app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))
    assert isinstance(started, BotCommandResult)
    assert started.accepted, started.message
    assert app.bot(bot_id).state is BotLifecycleState.RUNNING


def test_the_first_run_has_nothing_from_before(exchange: FakeExchange) -> None:
    with booted(exchange) as app:
        bot_id = _start(app)

        assert app.runtime(bot_id).earlier_runs_base == 0


def test_a_second_run_records_the_base_the_first_kept(exchange: FakeExchange) -> None:
    with booted(exchange) as app:
        bot_id = _start(app)
        first_run_base = _held(app)
        assert first_run_base > 0
        _stop_keeping_the_base(app, bot_id)

        _start_again(app, bot_id)

        runtime = app.runtime(bot_id)
        assert runtime.earlier_runs_base == first_run_base
        assert runtime.earlier_runs_cost > 0
        # The second run's own book holds only its own opening (ADR D6).
        assert _held(app) == first_run_base


def test_a_coin_sold_by_hand_between_the_runs_is_not_claimed(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _start(app)
        _stop_keeping_the_base(app, bot_id)
        spot = exchange.urls.spot_account
        left_by_hand = Decimal("0.004")
        spot.withdraw_free("BTC", spot.free_balance("BTC") - left_by_hand)

        _start_again(app, bot_id)

        assert app.runtime(bot_id).earlier_runs_base == left_by_hand
