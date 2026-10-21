"""`BOT-224` - above the 70 % line a ladder waits and the reads that guard exits are served.

@details `BUG-247`'s owner decision "C": the gate stays at 70 % for routine traffic and keeps a
reserve up to 90 % for a bot's position, the mark price and its open protective stops. The chain is
the composed app's own: the port, its service, the dispatcher, the query handler, the venue's
real session and gate, and the fake exchange, whose `X-MBX-USED-WEIGHT-1M` the gate reads. The
weight is moved the way a burst of ladder placement moves it, with requests the meter charges, and
the minute is held still (`BUG-232`)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance import (
    exchange_call_policy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.request_priority import (
    RequestPriority,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)

from .grid_fake_exchange import FakeExchange
from .two_venues_bots_world import FUTURES, booted_two_venues

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from fake_exchange.request_weight import WeightMeter

_LIMIT = 2400
_SOFT_LINE = int(_LIMIT * exchange_call_policy.SOFT_WEIGHT_RATIO)
_HARD_LINE = int(_LIMIT * exchange_call_policy.HARD_WEIGHT_RATIO)
_SYMBOL = "BTCUSDT"
_GUARD = RequestPriority.EXIT_GUARD


def _spend_up_to(meter: WeightMeter, weight: int) -> None:
    """Charge the minute with a ladder burst's worth of requests, short of `weight` by one read."""
    while meter.charge("GET", "/fapi/v1/openOrders", {}) < weight:
        pass


def _guard_reads(ports: VenueTradingPorts) -> None:
    ports.account_snapshot.open_positions(_GUARD)
    ports.order_entry_terms.mark_price_for(_SYMBOL, _GUARD)
    ports.account_activity.open_orders(_SYMBOL, _GUARD)


def test_a_ladder_burst_past_the_soft_line_leaves_the_guarding_reads_served(
    both_venues: FakeExchange,
) -> None:
    meter = both_venues.urls.weights
    meter.use_clock(lambda: 0.0)
    with booted_two_venues(both_venues) as app:
        ports = app.engine.context.container.resolve(IVenueTradingPorts).get(FUTURES)
        _spend_up_to(meter, _SOFT_LINE + 20)
        ports.account_snapshot.open_positions(_GUARD)  # its answer reports the weight

        before = meter.mark()
        with pytest.raises(ExchangeRateLimitedError):
            ports.account_activity.open_orders(_SYMBOL)
        refused_sent = meter.since(before)
        mark = meter.mark()
        _guard_reads(ports)

        served = {f"{r.method} {r.path}" for r in meter.since(mark)}
    assert refused_sent == (), "a ladder read waits at the 70 % line and is not sent"
    assert {
        "GET /fapi/v3/positionRisk",
        "GET /fapi/v1/premiumIndex",
        "GET /fapi/v1/openAlgoOrders",
    } <= served, f"the guards were not all sent: {sorted(served)}"


def test_past_the_hard_line_the_guards_wait_too(both_venues: FakeExchange) -> None:
    meter = both_venues.urls.weights
    meter.use_clock(lambda: 0.0)
    with booted_two_venues(both_venues) as app:
        ports = app.engine.context.container.resolve(IVenueTradingPorts).get(FUTURES)
        _spend_up_to(meter, _HARD_LINE + 20)
        ports.account_snapshot.open_positions(_GUARD)  # its answer reports the weight
        mark = meter.mark()

        with pytest.raises(ExchangeRateLimitedError):
            ports.account_snapshot.open_positions(_GUARD)
        with pytest.raises(MarketPriceRateLimitedError):
            ports.order_entry_terms.mark_price_for(_SYMBOL, _GUARD)

        assert meter.since(mark) == (), "a closed gate sends nothing"
