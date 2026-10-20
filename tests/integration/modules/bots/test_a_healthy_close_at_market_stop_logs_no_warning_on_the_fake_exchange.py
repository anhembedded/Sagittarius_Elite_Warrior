"""`BUG-233` - a Futures Grid stopped with a close ends flat, and nothing is warned about.

@details The stop's close empties the position and `STOP_CONFIRMED` clears the owner's book
before the account's flat report arrives. The session had learned the owner's position from the
exchange (a budgeted owner's orders never mark the symbol open), so that report corrects an
`open` belief nobody held wrongly: it is the bot's own close, not a mismatch. The run-log scan
fails a run with a WARNING.
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
from .futures_stop_helpers import started
from .grid_fake_exchange import FakeExchange


class _Warnings(logging.Handler):
    """The WARNING-or-worse records of the `App.*` loggers, which do not propagate to `caplog`."""

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(f"{record.name}: {record.getMessage()}")


@contextmanager
def _watching_warnings() -> Iterator[_Warnings]:
    handler, root = _Warnings(), logging.getLogger("App")
    root.addHandler(handler)
    try:
        yield handler
    finally:
        root.removeHandler(handler)


def test_a_stop_that_closes_the_position_logs_no_state_mismatch(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app, _watching_warnings() as warned:
        bot_id = started(app)
        app.move_price(62900)
        app.deliver()
        assert app.position() > 0

        stopped = app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, ExposureHandling.CLOSE_AT_MARKET)
        )
        app.deliver()

        assert isinstance(stopped, BotCommandResult) and stopped.accepted
        assert app.bot(bot_id).state is BotLifecycleState.STOPPED
        assert app.position() == 0
        assert warned.lines == []
