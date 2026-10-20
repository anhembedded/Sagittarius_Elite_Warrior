"""`EPIC-029J` J1b - a rate limit one bot of a venue meets reaches the bots beside it.

@details The exchange's pause is the venue's, not a bot's: the one gate (`ExchangeCallPolicy` /
`RateLimitGate`, `EPIC-035D`) refuses every caller of the venue for the stated pause. This is what
the neighbours do then, on the composed app over the fake exchange: each halts `RATE_LIMITED` at
the order its fill needs, never `ERROR` and never as a switch-off, and waits for the same pause
in AWAITING_RECOVERY (`EPIC-042F`: the recovery run's, with no timer of its own); a bot that needs no order keeps its ladder (a watch's refused read is
said and halts nothing); nothing is sent while the exchange asked for a pause; and the venue's
pause does not stop a bot on the other venue. Decision recorded in `EPIC-029J1b` §3b.
"""

from __future__ import annotations

import sys
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_retry_scheduler import (
    FakeBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

from .crowd_bots_world import FUTURES_SYMBOLS, run_bots
from .grid_fake_exchange import FakeExchange, ladder
from .two_venues_bots_world import FUTURES, SPOT, SYMBOL, booted_two_venues

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from fake_exchange.server import FaultAnswer

S = BotLifecycleState
THREE = FUTURES_SYMBOLS[:3]
#: What the exchange said: wait this long.
PAUSE_SECONDS = 30


def test_a_neighbour_halts_for_the_pause_at_the_first_order_it_needs_and_not_before(
    both_venues: FakeExchange, weight_gate_lifted: None
) -> None:
    retries = FakeBotRetryScheduler()
    with booted_two_venues(both_venues, retries=retries) as app:
        first, second, third = (run_bots(app, FUTURES, (s,))[s] for s in THREE)
        spot = run_bots(app, SPOT, (SYMBOL,))[SYMBOL]
        spot_ladder = app.resting(SPOT)
        sent_before = len(both_venues.urls.requests)
        both_venues.urls.faults.queued.append(
            FaultAnswer(
                "/fapi/v1/ping",
                status=429,
                body={"code": -1003, "msg": "Too many requests."},
                headers={"Retry-After": str(PAUSE_SECONDS)},
            )
        )

        app.move_price(
            FUTURES, 62_900, THREE[0]
        )  # the first bot's entry fills: its counter

        met = app.runtime(first)
        assert app.bot(first).state is S.AWAITING_RECOVERY, (
            met.reason,
            met.reason_detail,
        )
        assert met.reason is GridReason.RATE_LIMITED
        assert "resumes by itself" in met.reason_detail
        assert (app.bot(second).state, app.bot(third).state) == (
            S.RUNNING,
            S.RUNNING,
        ), "a bot that has sent nothing yet has nothing to halt for"

        app.move_price(
            FUTURES, 62_900, THREE[1]
        )  # the second bot's entry fills: its counter

        for bot_id in (first, second):
            runtime = app.runtime(bot_id)
            assert app.bot(bot_id).state is S.AWAITING_RECOVERY, (
                bot_id,
                runtime.reason_detail,
            )
            assert runtime.reason is GridReason.RATE_LIMITED, runtime.reason_detail
            assert "resumes by itself" in runtime.reason_detail

        app.monotonic.advance(5)
        app.ticker.fire()  # the beat: the third bot's reads meet the closed gate

        assert app.bot(third).state is S.RUNNING, (
            "a read the pause refused degrades the watch and is said; it halts nothing, and "
            "a halt would only cost the resume's cancel-all and fresh ladder"
        )
        assert both_venues.urls.futures_book.open_orders(THREE[2]), (
            "the third bot's ladder still rests on the exchange"
        )
        assert app.bot(spot).state is S.RUNNING, "the other venue has a gate of its own"
        assert app.resting(SPOT) == spot_ladder == set(ladder(app.runtime(spot)))

        assert [
            retry
            for retry in retries.pending
            if retry.delay.total_seconds() >= PAUSE_SECONDS
        ] == [], "the wait is the recovery run's: no resume timer is scheduled"
        sent = both_venues.urls.requests[sent_before:]
        assert ("DELETE", "/fapi/v1/order") not in sent
        assert all(
            not (method == "POST" and path.endswith("/order"))
            for method, path in sent
            if path.startswith("/fapi")
        ), "nothing is sent to the Futures venue while its exchange asked for a pause"
