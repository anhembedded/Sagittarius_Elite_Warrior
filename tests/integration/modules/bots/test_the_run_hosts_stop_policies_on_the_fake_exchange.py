"""`EPIC-038D` - the two stop policies on a live Grid, against the fake Binance server.

The unit tests prove each policy with a scripted bots world. This proves them on the
composed app with a real bot whose ladder really rests on the (fake) exchange:

  · `LeaveOrdersResting` asks the exchange for nothing - the ladder is exactly as it
    was, and the server saw no request that places or cancels (decision O1);
  · `StopBotsFirst` dispatches the Stop the screen dispatches: the bot's orders are
    cancelled, the bot reaches STOPPED, and the base is kept (no market sell).

Nothing here reaches a real exchange.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
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
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.leave_orders_resting import (
    LeaveOrdersResting,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.stop_bots_first import (
    StopBotsFirst,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_policy import (
    StopLedger,
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

S = BotLifecycleState
_PLACING_OR_CANCELLING = ("POST", "PUT", "DELETE")


class _Messages(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


@contextmanager
def _heard(logger_name: str) -> Iterator[list[str]]:
    """What a logger said. The composed app turns propagation off on `App`, so the
    records never reach pytest's root handler (`caplog`); a handler on the logger does."""
    handler = _Messages()
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    try:
        yield handler.lines
    finally:
        logger.removeHandler(handler)


def _started(app: BootedApp) -> str:
    created = app.engine.dispatch(
        CreateBotCommand, CreateBotCommand("grid", "grid", SPOT, SYMBOL, GRID)
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None
    started = app.engine.dispatch(StartBotCommand, StartBotCommand(created.bot_id))
    assert isinstance(started, BotCommandResult)
    assert started.accepted, started.message
    return created.bot_id


def _dispatcher(app: BootedApp) -> ICommandDispatcher:
    return app.engine.container.resolve(ICommandDispatcher)  # type: ignore[type-abstract, no-any-return]


def test_leave_orders_resting_places_and_cancels_nothing_on_the_fake_exchange(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _started(app)
        before_orders = resting(app.urls)
        before_requests = len(app.urls.requests)
        assert before_orders, "the ladder is on the exchange"

        with _heard("App.Operations.StopPolicy") as lines:
            LeaveOrdersResting(_dispatcher(app)).apply(StopLedger(), threading.Event())

        asked = app.urls.requests[before_requests:]
        assert not [r for r in asked if r[0] in _PLACING_OR_CANCELLING], asked
        assert resting(app.urls) == before_orders == ladder(app.runtime(bot_id))
        assert app.bot(bot_id).state is S.RUNNING
        text = "\n".join(lines)
        assert f"{bot_id} (RUNNING) {len(before_orders)} orders resting" in text


def test_stop_bots_first_stops_the_bot_the_way_the_screen_does_and_keeps_its_base(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _started(app)
        before_requests = len(app.urls.requests)
        ledger = StopLedger()

        StopBotsFirst(_dispatcher(app), poll_s=0).apply(ledger, threading.Event())
        app.deliver()

        assert app.bot(bot_id).state is S.STOPPED
        assert resting(app.urls) == {}
        assert ledger.left() == ()
        assert ledger.finished() == (bot_id,)
        asked = app.urls.requests[before_requests:]
        assert [r for r in asked if r[0] == "DELETE"], "the bot's orders were cancelled"
        # Keeping the base: no order was placed to sell it.
        assert not [r for r in asked if r[0] == "POST" and r[1].endswith("/order")], (
            asked
        )
