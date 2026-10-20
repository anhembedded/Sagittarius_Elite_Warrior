"""`BUG-216` - a Futures Grid whose order meets the exchange's pause waits it out; it is not switched off.

@details The owner's testnet log (2026-10-15): the exchange answered `-1003` to a burst, the app's
connection check filed that under "unclassified exception" (a `NETWORK` failure), the order gate
answered `connection_not_ready`, and the bot went `RUNNING -> HALTED on switch_off`, a halt that only
a person ends, with a position open and no exchange-side stop. The pause is not a switch-off: it is
the exchange asking for a minute, and `GridRateLimitPause` already knows what to do with that (halt
for exactly the pause, take nothing off the exchange because nothing can be sent, resume by itself).
Since `EPIC-042F` the wait is the halt-recovery mechanism's (AWAITING_RECOVERY): Futures lists the
exchange's pause as the one reason it recovers from, so the behaviour the owner saw is unchanged.

The journey runs the composed app and the production executor against the Futures testnet fake,
whose `FaultPlan` answers the connection check's first request with a 429 and a `Retry-After`.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

from .futures_bots_world import booted_futures_bots
from .futures_direction_scenarios import LONG
from .futures_fake_exchange import SYMBOL
from .grid_fake_exchange import FakeExchange
from .test_a_futures_grid_halts_and_recovers_on_the_fake_exchange import _started

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from fake_exchange.server import FaultAnswer

S = BotLifecycleState
#: What the exchange said: wait this long.
PAUSE_SECONDS = 30


def _answer_the_next_connection_check_with_a_pause(futures: FakeExchange) -> None:
    futures.urls.faults.queued.append(
        FaultAnswer(
            "/fapi/v1/ping",
            status=429,
            body={"code": -1003, "msg": "Too many requests."},
            headers={"Retry-After": str(PAUSE_SECONDS)},
        )
    )


def test_an_order_met_by_the_pause_holds_the_bot_for_the_pause_and_not_as_a_switch_off(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, LONG.config)
        mark = len(futures.urls.requests)
        _answer_the_next_connection_check_with_a_pause(futures)

        app.move_price(LONG.entry_price)  # an entry fills; its counter must be placed

        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.AWAITING_RECOVERY, (
            runtime.reason,
            runtime.reason_detail,
        )
        assert runtime.reason is GridReason.RATE_LIMITED, (
            f"{runtime.reason}: {runtime.reason_detail}"
        )
        assert "resumes by itself" in runtime.reason_detail
        sent = futures.urls.requests[mark:]
        assert ("DELETE", "/fapi/v1/order") not in sent, (
            "a halt for a pause cancels nothing: the cancel would be refused too"
        )
        assert all(
            not (method == "POST" and path == "/fapi/v1/order") for method, path in sent
        ), "nothing is sent while the exchange asked for a pause"


def _position_on_the_exchange(futures: FakeExchange) -> Decimal:
    """Read from the fake itself: the app's own client is refused during the pause."""
    rows = futures.urls.futures_book.account.position_risk(SYMBOL)
    return sum((Decimal(row["positionAmt"]) for row in rows), Decimal(0))


def test_the_position_a_pause_left_behind_is_not_closed_by_the_halt(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        _started(app, LONG.config)
        before = _position_on_the_exchange(futures)
        _answer_the_next_connection_check_with_a_pause(futures)

        app.move_price(LONG.entry_price)

        assert _position_on_the_exchange(futures) > before, "the entry filled"
        assert futures.urls.futures_book.open_orders(SYMBOL), (
            f"the {SYMBOL} ladder still rests on the exchange"
        )
