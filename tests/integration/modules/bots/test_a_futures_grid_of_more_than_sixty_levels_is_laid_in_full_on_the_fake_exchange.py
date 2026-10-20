"""`BUG-238` - a Futures Grid with more levels than the owner budget's orders a minute is laid in full.

@details The owner's testnet run (2026-10-20): a ladder of 60+ levels, the opening filled, and the
61st order of the minute met trading's `owner_budget_rate` refusal. The start read the refusal as
fatal (`start_refused`), cancelled the ladder and sold the position at market for a loss of fees
and spread. The pacer kept orders only a spacing (250 ms) apart, which is four times the budget's
60 a minute, so a ladder of any size above 60 ran into the wall.

The journey runs the composed app and the production executor against the Futures testnet fake,
with the production pacer on a virtual clock: its sleeps advance the time trading reads for its
rate window, so a minute of pacing costs the test no wait (`testing-rule.md`: no sleeps).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.monotonic_order_pacer import (
    MonotonicOrderPacer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
    OrderPacing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order import (
    handler,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .futures_bots_world import booted_futures_bots
from .futures_fake_exchange import FUTURES, SYMBOL
from .grid_fake_exchange import FakeExchange

S = BotLifecycleState

#: The owner budget's rate (ADR O1): orders a minute.
ORDERS_A_MINUTE = 60
#: Levels above the rate, so the ladder cannot be laid inside one minute whatever the pace.
LEVELS = 70
#: 70 grids across the fake's mark of 64,000: the level at the price stays EMPTY, the ones above
#: sell (the opening's position) and the ones below buy. 10,000 USDT at 3x reaches 30,000 over
#: 71 orders, each under trading's 500 a order and the symbol's 100 minimum.
GRID = {
    "lower": "62000",
    "upper": "66000",
    "grid_count": str(LEVELS),
    "spacing": "ARITHMETIC",
    "capital_quote": "10000",
    "direction": "LONG",
    "leverage": "3",
    "stop_loss": "price:50000",
    "take_profit": "price:80000",
}
#: Virtual seconds before which trading stamps late: the burst of the first 60 orders takes about
#: 15 s, and the next order waits for the window, so no two consecutive orders straddle it.
LAGGED_UNTIL = 30.0
EPOCH = datetime(2026, 10, 20, 6, 26, 17, tzinfo=UTC)


class VirtualTime:
    """One clock for the pacer and for trading's rate window; a sleep moves it."""

    def __init__(self, early_stamp_lag: float = 0.0) -> None:
        self.seconds = 0.0
        #: How much later than the pacer's turn trading stamps each of the first orders it
        #: judges (a cold terms read, the handler's lock): the later ones are stamped on the turn.
        #: The lag drops only where the pacer waits for the window, so the spacing between two
        #: consecutive orders is never shortened by it.
        self._early_stamp_lag = early_stamp_lag

    def monotonic(self) -> float:
        return self.seconds

    def sleep(self, seconds: float) -> None:
        self.seconds += seconds

    def now(self) -> datetime:
        lag = self._early_stamp_lag if self.seconds < LAGGED_UNTIL else 0.0
        return EPOCH + timedelta(seconds=self.seconds + lag)


#: Under the pacer's `STAMP_JITTER` (2 s) and over zero: the early orders are stamped this late.
LATE_EARLY_STAMPS = 1.5


@pytest.fixture(
    params=[0.0, LATE_EARLY_STAMPS], ids=["stamps-on-the-turn", "early-stamps-late"]
)
def virtual_time(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[VirtualTime]:
    """Trading reads `datetime.now(UTC)` at the moment it judges an order; the journey gives it
    the virtual time instead of the machine's. With late early stamps the 61st order is a window
    plus a moment after the first by the pacer's clock but inside the window by trading's: only
    the pacer's margin (`STAMP_JITTER`) keeps it from being refused."""
    time = VirtualTime(early_stamp_lag=request.param)

    class _VirtualDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def,override]
            return time.now()

    monkeypatch.setattr(handler, "datetime", _VirtualDatetime)
    yield time


def _pacers_on(
    time: VirtualTime,
) -> Callable[[TradingVenue, OrderPacing], IOrderPacer]:
    """The production pacer, one per venue and pacing, on the virtual clock."""
    built: dict[tuple[TradingVenue, OrderPacing], IOrderPacer] = {}

    def of(venue: TradingVenue, pacing: OrderPacing) -> IOrderPacer:
        if (venue, pacing) not in built:
            built[(venue, pacing)] = MonotonicOrderPacer(
                pacing, clock=time.monotonic, sleep=time.sleep
            )
        return built[(venue, pacing)]

    return of


def test_a_ladder_of_more_levels_than_the_rate_allows_is_laid_in_full_and_never_sold(
    futures: FakeExchange, virtual_time: VirtualTime
) -> None:
    with booted_futures_bots(futures, pacers=_pacers_on(virtual_time)) as app:
        created = app.engine.dispatch(
            CreateBotCommand,
            CreateBotCommand("sixty-plus levels", "grid", FUTURES, SYMBOL, GRID),
        )
        assert isinstance(created, BotCommandResult)
        assert created.bot_id is not None, created.message
        bot_id = created.bot_id

        started = app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))

        assert isinstance(started, BotCommandResult)
        assert started.accepted, started.message
        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.RUNNING, (
            app.bot(bot_id).state,
            runtime.reason,
            runtime.reason_detail,
        )
        assert len(app.resting()) == LEVELS, (
            "every level but the one at the price rests"
        )
        assert {o.client_order_id for o in runtime.open_orders} == set(app.resting())
        assert app.position() > 0, "the opening position was kept, not sold"
        assert ("DELETE", "/fapi/v1/order") not in app.exchange.urls.requests, (
            "nothing was cancelled"
        )
        assert (
            virtual_time.seconds
            >= 60 * (LEVELS + 1 - ORDERS_A_MINUTE) / ORDERS_A_MINUTE
        ), "the pacer waited for the window"
