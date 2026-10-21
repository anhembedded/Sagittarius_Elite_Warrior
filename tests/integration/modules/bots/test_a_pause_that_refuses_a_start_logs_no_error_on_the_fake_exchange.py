"""`BUG-257` - a start refused by the exchange's pause tells the pause, not an ERROR and a code.

@details `BUG-256`'s journey (a 429 on the order after the opening's first slice) leaves the bot
STOPPING. Before this fix the park of that refused start logged `ERROR ... taking the ladder off
failed` with a traceback for a ladder the bot never laid, and the reason led with the code
`inventory_unavailable` before it named the pause. The pause is told once, as `[exchange-pause]`
(`test_a_pause_is_told_once_not_as_errors_on_the_fake_exchange.py`), and a reason says what the
user can read: the exchange asked for a pause.
"""

from __future__ import annotations

import logging

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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)

from .futures_bots_world import GRID, BootedFuturesBots, booted_futures_bots
from .futures_fake_exchange import FUTURES, SYMBOL
from .grid_fake_exchange import FakeExchange
from .test_an_exchange_pause_in_the_openings_later_slice_closes_the_start_on_the_fake_exchange import (
    _pause_after_the_first_order,
)


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_a_start_refused_under_the_exchanges_pause_logs_no_error_and_names_the_pause(
    futures: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture = _Capture()
    app_of: list[BootedFuturesBots] = []
    _pause_after_the_first_order(monkeypatch, app_of, futures)
    with booted_futures_bots(futures) as app:
        app_of.append(app)
        # The boot configures the app's logging: the handler goes on once it has.
        app_log = logging.getLogger("App")
        app_log.addHandler(capture)
        try:
            created = app.engine.dispatch(
                CreateBotCommand,
                CreateBotCommand("paused opening", "grid", FUTURES, SYMBOL, GRID),
            )
            assert isinstance(created, BotCommandResult)
            assert created.bot_id is not None, created.message
            app.engine.dispatch(StartBotCommand, StartBotCommand(created.bot_id))
        finally:
            app_log.removeHandler(capture)

        runtime = app.runtime(created.bot_id)
        assert app.bot(created.bot_id).state is BotLifecycleState.STOPPING
        errors = [r.getMessage() for r in capture.records if r.levelno >= logging.ERROR]
        assert errors == []
        assert "inventory_unavailable" not in runtime.reason_detail
        assert "pause" in runtime.reason_detail.split(";")[0]
        assert "may still rest" not in runtime.reason_detail, (
            "the bot laid no ladder order"
        )
