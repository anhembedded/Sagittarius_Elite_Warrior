"""`BUG-256` - the exchange's pause after an opening slice filled closes the start, as the app's own does.

@details `BUG-254` made the app's own pacing a pause everywhere but one case: after an opening slice
filled, a resume re-derives the ladder from the position held and does not finish the opening, so it
would run a smaller grid than the plan the owner saw. The exchange's own pause (429, 418) did the same
thing through the same step: the second slice met the pause, the bot waited in AWAITING_RECOVERY with
half the opening and no protective stop (nothing can be sent during a pause), and resumed a grid one
upper level short. The reviewer of `BUG-254` found it (PR #691, round 3).

The journey runs the composed app and the production executor against the Futures testnet fake, and
answers the connection check of the order after the first with a 429 and a `Retry-After`, as
`BUG-216`'s journey does. The fake answers every later request normally, as the exchange does after
its pause, so the close the fix owes can go.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
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
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limit_gate import (
    RateLimitGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order

from .futures_bots_world import GRID, BootedFuturesBots, booted_futures_bots
from .futures_fake_exchange import FUTURES, SYMBOL
from .grid_fake_exchange import FakeExchange
from .quiet_exchange_readers import forget_the_kept_connection

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from fake_exchange.server import FaultAnswer

S = BotLifecycleState


def _held(futures: FakeExchange) -> Decimal:
    """The position on the fake itself: the app's own client is refused during the pause."""
    rows = futures.urls.futures_book.account.position_risk(SYMBOL)
    return sum((Decimal(row["positionAmt"]) for row in rows), Decimal(0))


def _pause_after_the_first_order(
    monkeypatch: pytest.MonkeyPatch,
    app_of: list[BootedFuturesBots],
    futures: FakeExchange,
) -> None:
    """The exchange answers the connection check of the order after the first with its pause: the
    first order goes, then the kept connection is forgotten and the next check meets the 429, as
    in `BUG-216`'s journey."""
    real = FuturesTradingClient.place_order
    sent: list[Order] = []

    def place_order(self: FuturesTradingClient, order: Order) -> Order:
        placed = real(self, order)
        sent.append(order)
        if len(sent) == 1:
            forget_the_kept_connection(app_of[0].engine.context.container, FUTURES)
            futures.urls.faults.queued.append(
                FaultAnswer(
                    "/fapi/v1/ping",
                    status=429,
                    body={"code": -1003, "msg": "Too many requests."},
                    headers={"Retry-After": "30"},
                )
            )
        return placed

    monkeypatch.setattr(FuturesTradingClient, "place_order", place_order)


def test_the_exchanges_pause_on_the_openings_second_slice_closes_the_start_and_keeps_no_half_grid(
    futures: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_of: list[BootedFuturesBots] = []
    _pause_after_the_first_order(monkeypatch, app_of, futures)
    with booted_futures_bots(futures) as app:
        app_of.append(app)
        created = app.engine.dispatch(
            CreateBotCommand,
            CreateBotCommand("paused opening", "grid", FUTURES, SYMBOL, GRID),
        )
        assert isinstance(created, BotCommandResult)
        assert created.bot_id is not None, created.message
        bot_id = created.bot_id

        app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))

        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.STOPPING, (
            app.bot(bot_id).state,
            runtime.reason,
            runtime.reason_detail,
        )
        assert runtime.reason is GridReason.START_REFUSED
        assert "retry 1 of" in runtime.reason_detail, (
            "the stop's own timed retry is scheduled"
        )
        assert _held(futures) > 0, (
            "nothing can be sent during the pause: the close waits"
        )

        # The pause ends. The close retries itself on the stop's own backoff (a unit test:
        # `test_grid_executor_rate_limit.py`); the journey asks the stop again, as a person would.
        monkeypatch.setattr(RateLimitGate, "remaining", lambda _gate: 0.0)
        app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, ExposureHandling.CLOSE_AT_MARKET)
        )
        app.deliver()

        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.STOPPED, (
            app.bot(bot_id).state,
            runtime.reason,
            runtime.reason_detail,
        )
        assert app.position() == 0, "the half opening was closed once the pause ended"
