"""`BUG-247` - two wide ladders laid together stay under the gate's line on the fake exchange.

@details The owner's VPS ran an ETHUSDT bot of about 48 grids and a BNBUSDT bot of about 83, and
paused every read near the end of a minute (`Used weight 1778 of 2400`). The idle bots were not
the cost (about 175 a minute each, `test_many_bots_on_one_venue_cost_on_the_fake_exchange.py`):
the cost was the connection check every order and every cancel made first, 7 weight, once per
level laid. The gate is the real one here (not lifted) and the minute is held still, so the
count is of weight, not of the wall clock's luck (`BUG-232`)."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle import (
    other_active_bot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance import (
    exchange_call_policy,
)

from .crowd_bots_world import FUTURES_SYMBOLS, create_bot, start_bot
from .grid_fake_exchange import FakeExchange
from .two_venues_bots_world import FUTURES, GRIDS, booted_two_venues

GATE_LINE = int(2400 * exchange_call_policy.SOFT_WEIGHT_RATIO)
#: The two ladders of the owner's run, as wide as the fake's mark lets them be.
LADDER_SIZES = (48, 83)
#: What ping, time and account may cost together over both starts: the reads the starts need
#: themselves (about 190 measured), not 7 for each of the 131 levels laid (1,163 before the fix).
CONNECTION_CHECK_BUDGET = 300


def _wide_grid(levels: int) -> dict[str, str]:
    return dict(
        GRIDS[FUTURES],
        lower="50000",
        upper="76000",
        grid_count=str(levels),
        capital_quote=str(levels * 100),
        leverage="2",
        stop_loss="price:45000",
        take_profit="price:90000",
    )


def test_two_wide_ladders_laid_in_one_minute_do_not_close_the_gate(
    both_venues: FakeExchange,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(other_active_bot, "MAX_ACTIVE_BOTS_PER_VENUE", 1_000)
    meter = both_venues.urls.weights
    meter.use_clock(lambda: 0.0)
    with booted_two_venues(both_venues) as app:
        mark = meter.mark()
        refused: list[str] = []
        for levels, symbol in zip(LADDER_SIZES, FUTURES_SYMBOLS, strict=False):
            started = start_bot(
                app, create_bot(app, FUTURES, symbol, params=_wide_grid(levels))
            )
            if not started.accepted:
                refused.append(f"{levels} levels: {started.message}")
        spent = meter.weight_since(mark)
        by_path = meter.by_path_since(mark)

    checks = sum(
        by_path[f"GET {path}"]
        for path in ("/fapi/v2/account", "/fapi/v1/time", "/fapi/v1/ping")
    )
    assert not refused, f"the gate closed on a start: {refused}"
    assert spent < GATE_LINE * 0.6, (
        f"laying {LADDER_SIZES} levels spent {spent} of the gate's {GATE_LINE}: {dict(by_path.most_common(5))}"
    )
    assert checks <= CONNECTION_CHECK_BUDGET, (
        f"the connection checks of the orders spent {checks}: one per level laid"
    )
