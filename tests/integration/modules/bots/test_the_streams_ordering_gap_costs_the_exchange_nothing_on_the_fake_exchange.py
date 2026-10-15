"""`BUG-216` - the account's report and the order's report may arrive in either order, and neither costs a read.

@details The owner's 2026-10-15 Futures testnet log: the account's report outran the order's, trading
reported a divergence for the seconds between them, and the watch's re-read registered the budget
again (positionRisk twice, the fills' history, the open orders) to learn what a few seconds later
told for free. The book now answers from the figure the stream last reported, so a gap that closes
by itself is never read, while a divergence that does not close is read as before and the exchange
decides: a position nobody here opened still halts the bot.

The reads are told by the requests the fake exchange received (`WeightMeter`): a registration is the
only caller of the fills' history, so one `userTrades` request is one registration.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.owner_position_diverged_event import (
    OwnerPositionDivergedEvent,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .futures_bots_world import BootedFuturesBots, booted_futures_bots
from .futures_direction_scenarios import LONG
from .futures_fake_exchange import SYMBOL
from .grid_fake_exchange import FakeExchange
from .test_a_futures_grid_halts_and_recovers_on_the_fake_exchange import (
    _publish_tick,
    _started,
)
from .test_every_direction_passes_the_shared_journeys_on_the_fake_exchange import (
    _by_hand,
)

D = Decimal
S = BotLifecycleState
#: Longer than `FuturesGridThresholds.position_recheck_delay`.
RECHECK_DELAY_PASSES = 6
#: The paths a registration reads that nothing else on a running bot does.
REGISTRATION_PATHS = {"/fapi/v1/userTrades"}


def _registrations_since(app: BootedFuturesBots, mark: int) -> int:
    return sum(
        1 for r in app.exchange.urls.weights.since(mark) if r.path in REGISTRATION_PATHS
    )


def _account_report_first(events: list[dict]) -> list[dict]:
    return sorted(events, key=lambda event: event.get("e") != "ACCOUNT_UPDATE")


def _order_report_first(events: list[dict]) -> list[dict]:
    return sorted(events, key=lambda event: event.get("e") == "ACCOUNT_UPDATE")


def _deliver(app: BootedFuturesBots, events: list[dict]) -> None:
    for event in events:
        asyncio.run(app.stream._handle_message(event))


def _the_recheck_delay_passes(app: BootedFuturesBots) -> None:
    _publish_tick(app, float(LONG.entry_price))
    app.monotonic.advance(RECHECK_DELAY_PASSES)
    app.ticker.fire()
    app.deliver()


def _the_entry_fills(app: BootedFuturesBots) -> list[dict]:
    app.exchange.urls.futures_book.move_price(SYMBOL, LONG.entry_price)
    return app.exchange.urls.futures_book.drain_user_data_events()


def _diverged_events(app: BootedFuturesBots) -> list[OwnerPositionDivergedEvent]:
    seen: list[OwnerPositionDivergedEvent] = []
    app.engine.context.container.resolve(IEventBus).on(
        OwnerPositionDivergedEvent, seen.append
    )
    return seen


@pytest.mark.parametrize(
    "account_first", (False, True), ids=("fill_first", "account_first")
)
def test_a_fill_and_the_accounts_report_in_either_order_leave_the_bot_running_and_read_nothing(
    futures: FakeExchange, account_first: bool
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, LONG.config)
        diverged = _diverged_events(app)
        events = _the_entry_fills(app)
        mark = app.exchange.urls.weights.mark()

        _deliver(
            app,
            _account_report_first(events)
            if account_first
            else _order_report_first(events),
        )
        _the_recheck_delay_passes(app)

        assert bool(diverged) is account_first, "only the account-first order is a gap"
        assert _registrations_since(app, mark) == 0
        assert app.bot(bot_id).state is S.RUNNING
        assert (
            app.runtime(bot_id).inventory == app.position() == LONG.position_after_entry
        )


def test_a_fill_reported_twice_is_counted_once_and_read_nothing(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, LONG.config)
        events = _the_entry_fills(app)
        mark = app.exchange.urls.weights.mark()

        _deliver(app, _account_report_first(events))
        _deliver(app, _order_report_first(events))  # the same reports again
        _the_recheck_delay_passes(app)

        assert _registrations_since(app, mark) == 0
        assert app.bot(bot_id).state is S.RUNNING
        assert (
            app.runtime(bot_id).inventory == app.position() == LONG.position_after_entry
        )


def test_a_lost_order_report_is_read_and_the_exchanges_record_settles_it(
    futures: FakeExchange,
) -> None:
    """The gap that does not close by itself: the account reported the fill, the order's report
    never came. The book cannot agree, so the watch reads the exchange as it always did, and the
    registration derives the fill from the exchange's own record."""
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, LONG.config)
        events = _the_entry_fills(app)
        mark = app.exchange.urls.weights.mark()

        _deliver(app, [e for e in events if e.get("e") == "ACCOUNT_UPDATE"])
        _the_recheck_delay_passes(app)

        assert _registrations_since(app, mark) == 1
        assert app.bot(bot_id).state is S.RUNNING


def test_a_position_nobody_here_opened_is_read_and_halts_the_bot(
    futures: FakeExchange,
) -> None:
    """The in-memory answer can only close a divergence: a trade by hand moves the exchange's
        amount with no fill of the bot's, the book never agrees with the figure the stream reported,
        the exchange is read, and the position it still finds foreign halts the bot (`POSITION_MISMATCH`: the
    re-read's own words for it)."""
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, LONG.config)
        mark = app.exchange.urls.weights.mark()

        _by_hand(app, LONG, "0.003")
        app.deliver()
        _the_recheck_delay_passes(app)

        assert _registrations_since(app, mark) >= 1
        assert app.runtime(bot_id).reason in {
            GridReason.FOREIGN_FILL,
            GridReason.POSITION_MISMATCH,
        }, "a divergence the exchange confirmed, in the words of the re-read"
        assert app.bot(bot_id).state is not S.RUNNING


def test_a_burst_with_the_accounts_report_first_ends_with_no_registration_read(
    futures: FakeExchange,
) -> None:
    """The owner's burst: twelve fills, each reported by the account before the order. Every
    report raised a divergence (`BUG-218` keeps one re-read pending for them); when it is due the
    book has caught up and nothing is registered again. The weight of the whole burst and its
    re-read stays inside the per-fill budget `BUG-216` set."""
    cycles, per_fill_budget = 6, 25
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, LONG.config)
        book = app.exchange.urls.futures_book
        mark = app.exchange.urls.weights.mark()

        for _ in range(cycles):
            for price in (LONG.entry_price, LONG.completion_price):
                book.move_price(SYMBOL, price)
                _deliver(app, _account_report_first(book.drain_user_data_events()))
        _the_recheck_delay_passes(app)

        assert _registrations_since(app, mark) == 0
        assert (
            app.exchange.urls.weights.weight_since(mark) <= 2 * cycles * per_fill_budget
        )
        assert app.bot(bot_id).state is S.RUNNING
