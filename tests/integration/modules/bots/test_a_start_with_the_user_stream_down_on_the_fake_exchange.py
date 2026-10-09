"""`BUG-194` — a Grid's start while the user data stream says nothing.

@details Trading counts the base a bot bought only from the venue's reports, so a
stream that is down, or later than the next order, left the owner's inventory at
zero: the first SELL of the ladder was refused (`owner_budget_sell_exceeds_inventory`)
and the bot halted at once, with the opening buy already paid for. The bot now
asks trading to count the opening buy from the exchange's own record of it
before it lays a SELL, and the stream's late report of the same fill is not
counted a second time.

The composed app over the fake Binance server, with a pacer that delivers no
report (`booted(stream_up=False)`): the journey is the owner's, Start on an
account whose stream never answers.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
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
    BootedApp,
    FakeExchange,
    booted,
    ladder,
    resting,
)


def _start(app: BootedApp) -> str:
    created = app.engine.dispatch(
        CreateBotCommand, CreateBotCommand("grid", "grid", SPOT, SYMBOL, GRID)
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None
    started = app.engine.dispatch(StartBotCommand, StartBotCommand(created.bot_id))
    assert isinstance(started, BotCommandResult)
    assert started.accepted, started.message
    return created.bot_id


def _held(app: BootedApp) -> Decimal:
    (share,) = app.scope.session_state.owner_books.shares()
    return share.inventory.quantity


def test_a_start_whose_stream_is_silent_still_lays_its_sells(
    exchange: FakeExchange,
) -> None:
    with booted(exchange, stream_up=False) as app:
        bot_id = _start(app)

        reason = app.runtime(bot_id).reason_detail
        assert app.bot(bot_id).state is BotLifecycleState.RUNNING, reason
        assert resting(app.urls) == ladder(app.runtime(bot_id))
        assert {side for side, _ in resting(app.urls).values()} == {"BUY", "SELL"}


def test_the_stream_reporting_the_opening_buy_late_does_not_count_it_twice(
    exchange: FakeExchange,
) -> None:
    with booted(exchange, stream_up=False) as app:
        _start(app)
        counted_from_the_exchange = _held(app)
        assert counted_from_the_exchange > 0

        app.deliver()  # the stream comes back and reports what it missed

        assert _held(app) == counted_from_the_exchange
