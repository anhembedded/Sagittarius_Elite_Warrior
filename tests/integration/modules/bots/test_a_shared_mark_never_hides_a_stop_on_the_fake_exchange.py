"""`BOT-221` - the two watches of a bot share one mark reading a beat, and no stop is hidden by it.

@details The composed app over the Futures testnet fake (`futures_bots_world`, `crowd_bots_world`):
the production executor, the production watches and the fake's matcher. The mark guards a stop
loss, a take profit and the risk watch, so the reading is served for at most half a beat and is
dropped by any order or fill of the symbol; the open orders the protective-stop check reads are
not shared, and the absence of a stop is still judged on the account (`BOT-184`). The measured
test writes the weight table of an idle minute at 1, 5 and 20 bots.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_account_reads import (
    BotAccountReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.bot_price_watch import (
    CHECK_EVERY_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

from .crowd_bots_world import FUTURES_SYMBOLS, run_bots
from .futures_bots_world import booted_futures_bots
from .futures_fake_exchange import SYMBOL
from .futures_stop_helpers import STOP_LOSS, started, stops
from .grid_fake_exchange import FakeExchange
from .test_many_bots_on_one_venue_cost_on_the_fake_exchange import (
    BEATS_PER_MINUTE,
    COUNTS,
    FUTURES_WEIGHT,
    GATE_LINE,
    _an_idle_minute,
    gate_never_closes,
    report,
)
from .two_venues_bots_world import FUTURES, booted_two_venues

S = BotLifecycleState
MARK_PATH = "GET /fapi/v1/premiumIndex"
OPEN_ORDERS_PATH = "GET /fapi/v1/openOrders"
__all__ = ["gate_never_closes", "report"]  # fixtures re-exported for pytest


def test_the_two_watches_of_a_beat_read_the_mark_once(futures: FakeExchange) -> None:
    """Both watches of the bot (exit and risk) ask the venue for its symbol's mark each beat: it
    was two `premiumIndex` requests, it is one."""
    meter = futures.urls.weights
    with booted_futures_bots(futures) as app:
        started(app)
        mark = meter.mark()

        app.monotonic.advance(CHECK_EVERY_SECONDS)
        app.ticker.fire()

        assert meter.by_path_since(mark)[MARK_PATH] == 1


def test_a_second_look_inside_half_a_beat_takes_the_reading_a_look_after_a_beat_reads_again(
    futures: FakeExchange,
) -> None:
    meter = futures.urls.weights
    with booted_futures_bots(futures) as app:
        started(app)
        app.monotonic.advance(CHECK_EVERY_SECONDS)
        app.ticker.fire()
        mark = meter.mark()

        app.ticker.fire()  # the same instant: nothing is older than half a beat
        assert meter.by_path_since(mark)[MARK_PATH] == 0

        app.monotonic.advance(CHECK_EVERY_SECONDS)
        app.ticker.fire()
        assert meter.by_path_since(mark)[MARK_PATH] == 1


def test_a_fill_between_two_looks_drops_the_mark(futures: FakeExchange) -> None:
    """The bot's own buy fills inside the window: the next look reads the mark, not the reading
    taken before the fill."""
    meter = futures.urls.weights
    with booted_futures_bots(futures) as app:
        started(app)
        app.monotonic.advance(CHECK_EVERY_SECONDS)
        app.ticker.fire()  # the mark is read and shared
        app.move_price(Decimal(63000))  # a resting buy fills; the stream tells the bot
        mark = meter.mark()

        app.ticker.fire()

        assert meter.by_path_since(mark)[MARK_PATH] == 1


def test_a_fill_between_two_looks_that_this_app_never_hears_still_leaves_the_reading_half_a_beat_old(
    futures: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The limit, told by a test: with every drop switched off a look inside the window is served
    the reading, never one older than half a beat."""
    monkeypatch.setattr(BotAccountReads, "account_changed", lambda self: None)
    meter = futures.urls.weights
    with booted_futures_bots(futures) as app:
        started(app)
        app.monotonic.advance(CHECK_EVERY_SECONDS)
        app.ticker.fire()
        app.move_price(Decimal(63000))
        mark = meter.mark()

        app.ticker.fire()
        assert meter.by_path_since(mark)[MARK_PATH] == 0

        app.monotonic.advance(CHECK_EVERY_SECONDS / 2)
        app.ticker.fire()
        assert meter.by_path_since(mark)[MARK_PATH] == 1


def test_a_stop_that_runs_between_two_beats_ends_the_bot_as_triggered_with_the_mark_shared(
    futures: FakeExchange,
) -> None:
    """A beat has just read the mark and the positions (both shared); the exchange's stop runs
    right after. The stop is told as run and the bot ends flat, as when nothing is shared."""
    with booted_futures_bots(futures) as app:
        bot_id = started(app)
        futures.urls.futures_book.faults.hold_fills = True
        app.monotonic.advance(CHECK_EVERY_SECONDS)
        app.ticker.fire()

        app.move_price(STOP_LOSS - 100)

        assert app.position() == 0
        assert app.bot(bot_id).state is S.STOPPED
        assert app.runtime(bot_id).reason is GridReason.PROTECTIVE_STOP_TRIGGERED
        assert stops(app) == []


def test_a_stop_cancelled_by_hand_between_two_beats_is_seen_and_placed_again_at_once(
    futures: FakeExchange,
) -> None:
    """The open orders the stop check reads are not shared: a stop taken off the exchange right
    after a beat shared the mark and the positions is missing to the very next look."""
    meter = futures.urls.weights
    with booted_futures_bots(futures) as app:
        started(app)
        app.monotonic.advance(CHECK_EVERY_SECONDS)
        app.ticker.fire()
        futures.urls.futures_book.algo.cancel_all(SYMBOL)
        mark = meter.mark()

        app.ticker.fire()

        assert meter.by_path_since(mark)[OPEN_ORDERS_PATH] == 1
        assert len(stops(app)) == 1


@pytest.mark.parametrize("count", COUNTS)
def test_n_idle_bots_read_each_mark_once_a_beat(
    both_venues: FakeExchange,
    gate_never_closes: None,
    count: int,
    report: Callable[[str], None],
) -> None:
    """`BOT-221`: it was two `premiumIndex` reads a beat per bot (24 weight a minute each)."""
    meter = both_venues.urls.weights
    with booted_two_venues(both_venues) as app:
        symbols = FUTURES_SYMBOLS[:count]
        run_bots(app, FUTURES, symbols)
        mark = meter.mark()

        _an_idle_minute(app, symbols)
        spent = meter.weight_since(mark)
        by_path = meter.by_path_since(mark)

    marks = by_path[MARK_PATH]
    report(
        f"MEASURED idle minute N={count}: {spent} weight = {spent / count:.0f} per bot "
        f"({spent / GATE_LINE:.0%} of the gate's {GATE_LINE}, {spent / FUTURES_WEIGHT:.0%} of "
        f"the exchange's {FUTURES_WEIGHT}); mark {marks}, open orders "
        f"{by_path[OPEN_ORDERS_PATH]}, algo {by_path['GET /fapi/v1/openAlgoOrders']}, "
        f"positions {by_path['GET /fapi/v3/positionRisk']}"
    )
    assert marks <= (BEATS_PER_MINUTE + 1) * count, (
        f"{count} idle bots spent {marks} weight a minute reading marks: more than one read a "
        "beat each"
    )
