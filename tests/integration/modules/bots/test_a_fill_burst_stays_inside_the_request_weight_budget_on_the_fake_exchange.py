"""`BUG-216` - a burst of fills on a Futures Grid spends a small share of the exchange's request weight.

@details The owner's Futures testnet log (2026-10-15) spent ~2,170 of the 2,400 weight a minute in
about a minute, set off by the price crossing three levels back and forth, and the exchange banned
the IP (`-1003`). The fake exchange charges every request its Binance weight (`WeightMeter`) and
reports the minute's total in `X-MBX-USED-WEIGHT-1M`, as the exchange does, so what a journey
costs is a figure a test can bound. Measured before the fix, a burst of 12 fills cost 1,038:
720 of it `positionSide/dual` (30 a read), read by the connection check that gates every order and
every cancel; a reconcile or a re-read added 80 for two unfiltered open-orders reads.

The budgets below are derived, not tuned: a fill is a handful of requests at weight 1-5, so a
fill that costs more than `PER_FILL_BUDGET` is reading something it does not need to.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)

from .futures_bots_world import BootedFuturesBots, booted_futures_bots
from .futures_direction_scenarios import LONG
from .futures_fake_exchange import FUTURES, SYMBOL
from .grid_fake_exchange import FakeExchange
from .test_a_futures_grid_halts_and_recovers_on_the_fake_exchange import _started

D = Decimal

#: Weight a fill may cost the whole app: its counter order's gate, the account's position and the
#: mark read around it. 2,400 a minute over this is 96 fills a minute, far above a busy grid.
PER_FILL_BUDGET = 25
#: One entry and its completion, six times: twelve fills across the ladder.
CYCLES = 6
#: The owner's burst delivered the account's report ahead of the order's, the order testnet sends
#: them in; the app must spend the same either way.
ACCOUNT_REPORT_FIRST = (True, False)


def _unscoped_open_order_reads(
    app: BootedFuturesBots, mark: int
) -> list[tuple[str, str]]:
    """Open-order reads after `mark` that named no symbol: 40 weight each, and a bot has one."""
    meter = app.exchange.urls.weights
    return [
        (r.method, r.path)
        for r in meter.since(mark)
        if r.path in {"/fapi/v1/openOrders", "/fapi/v1/openAlgoOrders"}
        and not r.with_symbol
    ]


def _deliver(app: BootedFuturesBots, *, account_report_first: bool) -> None:
    events = app.exchange.urls.futures_book.drain_user_data_events()
    if account_report_first:
        events.sort(key=lambda event: event.get("e") != "ACCOUNT_UPDATE")
    for event in events:
        asyncio.run(app.stream._handle_message(event))


def _burst(app: BootedFuturesBots, *, account_report_first: bool) -> int:
    book = app.exchange.urls.futures_book
    for _ in range(CYCLES):
        for price in (LONG.entry_price, LONG.completion_price):
            book.move_price(SYMBOL, price)
            _deliver(app, account_report_first=account_report_first)
    return 2 * CYCLES


@pytest.mark.parametrize("account_first", ACCOUNT_REPORT_FIRST)
def test_a_burst_of_fills_costs_each_fill_a_small_share_of_the_weight_budget(
    futures: FakeExchange, account_first: bool
) -> None:
    with booted_futures_bots(futures) as app:
        _started(app, LONG.config)
        meter = futures.urls.weights
        mark = meter.mark()

        fills = _burst(app, account_report_first=account_first)

        spent = meter.weight_since(mark)
        by_path = dict(meter.by_path_since(mark).most_common(4))
        assert spent <= fills * PER_FILL_BUDGET, (
            f"{spent} weight for {fills} fills "
            f"(account report first: {account_first}); most spent by {by_path}"
        )


def test_the_connection_check_that_gates_orders_does_not_read_the_position_mode_per_order(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        _started(app, LONG.config)
        meter = futures.urls.weights
        mark = meter.mark()

        orders = _burst(app, account_report_first=False)

        mode_reads = [
            r for r in meter.since(mark) if r.path == "/fapi/v1/positionSide/dual"
        ]
        assert len(mode_reads) < orders, (
            f"{len(mode_reads)} position-mode reads (30 weight each) for {orders} fills: "
            "the gate re-reads an account setting per order"
        )


def test_a_stream_reconcile_reads_the_bots_own_symbol_and_not_the_whole_account(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        _started(app, LONG.config)
        meter = futures.urls.weights
        mark = meter.mark()

        app.engine.event_bus.emit(
            UserStreamHealthEvent(
                UserStreamState.CONNECTED, datetime.now(UTC), 1, venue=FUTURES
            )
        )

        assert _unscoped_open_order_reads(app, mark) == [], (
            "a reconcile asked for every symbol's open orders (80 weight) "
            "to keep the bot's one"
        )
        assert meter.weight_since(mark) <= 60, dict(
            meter.by_path_since(mark).most_common(4)
        )
