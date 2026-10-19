"""`BUG-226` - a protective stop the exchange no longer holds is cancelled quietly.

@details After a halt closed the position the owner's journal showed `ERROR ... cancel <stop> raised`
for the bot's protective stop, then `dropped`, then STOPPED: right outcome, wrong severity. The stop
is an algo order; a cancel of an id neither the regular nor the algo book holds is the exchange's
unknown-order refusal, which `BotOrderGateway.cancel` reads as `GONE` (`BUG-229`). This runs the
whole path on the Futures fake with the stop cancelled out of band: the bot ends STOPPED and flat,
the record is dropped, and nothing is logged at ERROR.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)

from .futures_bots_world import booted_futures_bots
from .futures_fake_exchange import SYMBOL
from .futures_stop_helpers import started, stops
from .grid_fake_exchange import FakeExchange


class _Errors(logging.Handler):
    """The ERROR-or-worse records of the `App.*` loggers, which do not propagate to `caplog`."""

    def __init__(self) -> None:
        super().__init__(logging.ERROR)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(f"{record.name}: {record.getMessage()}")


@contextmanager
def _watching_errors() -> Iterator[_Errors]:
    handler, root = _Errors(), logging.getLogger("App")
    root.addHandler(handler)
    try:
        yield handler
    finally:
        root.removeHandler(handler)


def test_a_stop_that_is_already_gone_is_cancelled_without_an_error(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app, _watching_errors() as errors:
        bot_id = started(app)
        assert len(stops(app)) == 1
        futures.urls.futures_book.algo.cancel_all(
            SYMBOL
        )  # gone before the bot cancels it

        stopped = app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, ExposureHandling.CLOSE_AT_MARKET)
        )
        app.deliver()

        assert isinstance(stopped, BotCommandResult) and stopped.accepted
        assert app.bot(bot_id).state is BotLifecycleState.STOPPED
        assert app.position() == 0
        assert app.runtime(bot_id).protective_stops == ()
        assert errors.lines == []
