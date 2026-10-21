"""`BUG-254` - a start whose orders trading stamps unevenly is not refused by the budget's spacing.

@details The owner's mainnet run (2026-10-21, BNBUSDT LONG, 27 levels): the opening filled, two
ladder orders were placed and the third, sent exactly 250 ms after the second by the pacer's clock,
met trading's `owner_budget_spacing`. The start read the pacing refusal as fatal (`start_refused`),
cancelled the ladder and sold the position at market for a loss.

The pacer schedules each order's turn 250 ms after the previous turn; trading stamps an order when
it judges it, a moment after its turn that differs from order to order (a sleep that overshoots,
the handler's lock, a cold terms read), and refuses one stamped less than 250 ms after the
previous stamp. Two orders whose stamps lag by different amounts are therefore closer than the
spacing however exactly the pacer spaces its turns. The stamp jitter below is that, and it is
enough: the production limits, the production pacer and the production handler, the clock virtual
(`testing-rule.md`: no sleeps).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    StartBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

from .futures_bots_world import GRID, booted_futures_bots
from .futures_fake_exchange import FUTURES, SYMBOL
from .futures_stop_helpers import stops
from .grid_fake_exchange import GRID as SPOT_GRID
from .grid_fake_exchange import SPOT, FakeExchange, booted
from .virtual_order_time import (
    PRODUCTION_PACING,
    VirtualTime,
    pacers_on,
    trading_reads,
)

S = BotLifecycleState

#: Seconds trading stamps after the pacer's turn, order by order. Each pair puts the second stamp
#: less than 250 ms after the first (the owner's gap was a few milliseconds short).
JITTERS = {
    "a-slow-send-then-a-quick-one": [0.030, 0.0],
    "a-few-milliseconds-short": [0.004, 0.0],
    "every-third-order-is-slow": [0.0, 0.0, 0.120],
}


#: The two doors to the one start: the Bots tab's Start, and the headless host's `bot start` /
#: `run --start-planned` (`EPIC-038K`), which dispatches the screen's own command after its checks.
STARTS = {
    "screen start": lambda bot_id: (StartBotCommand, StartBotCommand(bot_id)),
    "host start": lambda bot_id: (
        StartBotForHostCommand,
        StartBotForHostCommand(bot_id),
    ),
}


@pytest.mark.parametrize("start", STARTS.values(), ids=STARTS.keys())
@pytest.mark.parametrize("jitter", JITTERS.values(), ids=JITTERS.keys())
def test_a_start_whose_orders_are_stamped_unevenly_lays_its_ladder_and_keeps_its_position(
    futures: FakeExchange,
    monkeypatch: pytest.MonkeyPatch,
    jitter: list[float],
    start: Callable[[str], tuple[type, object]],
) -> None:
    time = VirtualTime(stamp_jitter=jitter)
    trading_reads(monkeypatch, time)
    with booted_futures_bots(
        futures, pacers=pacers_on(time), limits=PRODUCTION_PACING
    ) as app:
        created = app.engine.dispatch(
            CreateBotCommand,
            CreateBotCommand("uneven stamps", "grid", FUTURES, SYMBOL, GRID),
        )
        assert isinstance(created, BotCommandResult)
        assert created.bot_id is not None, created.message
        bot_id = created.bot_id

        command_type, command = start(bot_id)
        started = app.engine.dispatch(command_type, command)

        assert isinstance(started, BotCommandResult)
        assert started.accepted, started.message
        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.RUNNING, (
            app.bot(bot_id).state,
            runtime.reason,
            runtime.reason_detail,
        )
        assert app.position() > 0, "the opening position was kept, not sold"
        assert ("DELETE", "/fapi/v1/order") not in app.exchange.urls.requests, (
            "nothing was cancelled"
        )


def test_turns_that_keep_missing_pause_the_start_and_sell_nothing(
    futures: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When four turns in a row are found too soon, the pacer is wrong by seconds and not by a
    stamp's milliseconds. The start waits as for the exchange's pause (`EPIC-042F`) and sells
    nothing. The miss here is the opening's own second slice, before the sequence's protective stop
    stands: the stop is placed first (trading exempts it from pacing), so the position kept
    open meanwhile is never bare."""
    # Each stamp 0.3 s earlier than the last: every retry is closer to the previous stamp.
    time = VirtualTime(stamp_jitter=[12 - 0.3 * i for i in range(30)])
    trading_reads(monkeypatch, time)
    with booted_futures_bots(
        futures, pacers=pacers_on(time), limits=PRODUCTION_PACING
    ) as app:
        created = app.engine.dispatch(
            CreateBotCommand,
            CreateBotCommand("missed turns", "grid", FUTURES, SYMBOL, GRID),
        )
        assert isinstance(created, BotCommandResult)
        assert created.bot_id is not None, created.message
        bot_id = created.bot_id

        app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))

        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.AWAITING_RECOVERY, (
            app.bot(bot_id).state,
            runtime.reason,
            runtime.reason_detail,
        )
        assert runtime.reason is GridReason.RATE_LIMITED
        assert app.position() > 0, "the opening position was not sold"
        assert ("DELETE", "/fapi/v1/order") not in app.exchange.urls.requests
        assert len(stops(app)) == 1, "the position kept open has its protective stop"


@pytest.mark.parametrize("jitter", JITTERS.values(), ids=JITTERS.keys())
def test_a_spot_start_whose_orders_are_stamped_unevenly_lays_its_ladder(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch, jitter: list[float]
) -> None:
    """The same race on Spot, whose opening is a paced market BUY: the family is the seam, not
    the venue."""
    time = VirtualTime(stamp_jitter=jitter)
    trading_reads(monkeypatch, time)
    with booted(exchange, pacers=pacers_on(time), limits=PRODUCTION_PACING) as app:
        created = app.engine.dispatch(
            CreateBotCommand,
            CreateBotCommand("uneven stamps", "grid", SPOT, "BTCUSDT", SPOT_GRID),
        )
        assert isinstance(created, BotCommandResult)
        assert created.bot_id is not None, created.message
        bot_id = created.bot_id

        started = app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))

        assert isinstance(started, BotCommandResult)
        assert started.accepted, started.message
        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.RUNNING, (
            app.bot(bot_id).state,
            runtime.reason,
            runtime.reason_detail,
        )
