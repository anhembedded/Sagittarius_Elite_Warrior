"""`EPIC-047H` - a simulated venue and a simulated host clock for the refresh tests.

One `SimulatedVenue` is at once the venue's weight meter (what the used-weight header says), the bots' own
background load and the exchange the refresh reads from: each read adds its true cost to the minute's
used weight, the minute resets on the minute boundary, and the gate closes to routine requests from 70 %
of the limit, as `ExchangeCallPolicy` does. `drive` runs the refresher's `step()` the way its worker does,
sleeping the time `step()` asks for, so a thirty-minute run takes no time.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_read_refresh import (
    IBotReadRefresh,
    RefreshOutcome,
    RefreshScope,
    RefreshTarget,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_facts_refresher import (
    FactsRefresher,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.vps_feed_settings import (
    VpsFeedSettings,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_weight_meter import (
    IVenueWeightMeter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.weight_reading import (
    WeightReading,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

VENUE = TradingVenue.FUTURES_TESTNET
LIMIT = 2400
#: A minute boundary, so a run starts at second 0 of a minute.
WALL_START = 1_800_000_000.0 - (1_800_000_000.0 % 60)
SOFT_LINE = 0.7


class SimulatedClock:
    def __init__(self) -> None:
        self.seconds = 0.0

    def monotonic(self) -> float:
        return self.seconds

    def wall(self) -> float:
        return WALL_START + self.seconds


@dataclass
class SimulatedVenue(IVenueWeightMeter):
    clock: SimulatedClock
    background_per_minute: int = 0
    closed_by_hand: bool = False
    _minute: int = -1
    _used: int = 0
    _seen_at: float | None = None
    #: (second, true weight) of every read the refresh made.
    refresh_spend: list[tuple[float, int]] = field(default_factory=list)

    def read(self) -> WeightReading:
        # The header holds what the last answer said; it does not roll with the clock (`ExchangeCallPolicy._last_used`).
        routine_open = not self.closed_by_hand and self._used < LIMIT * SOFT_LINE
        return WeightReading(
            self._used if self._seen_at is not None else None,
            LIMIT,
            self._seen_at,
            routine_open,
        )

    def spend(self, weight: int, *, ours: bool, header: bool = True) -> None:
        """`header` false: a request the venue's call policy does not carry (`market_data`'s own client), which
        counts against the IP's minute but never reaches the used-weight header the refresher reads."""
        self._roll()
        if header:
            self._used += weight
            self._seen_at = self.clock.wall()
        if ours:
            self.refresh_spend.append((self.clock.seconds, weight))

    def worst_window(self, since: float = 0.0) -> int:
        """The most weight the refresh spent inside any 60-second window that starts at or after `since`."""
        return max(
            (
                sum(w for t, w in self.refresh_spend if start <= t < start + 60)
                for start, _ in self.refresh_spend
                if start >= since
            ),
            default=0,
        )

    def _roll(self) -> None:
        minute = int(self.clock.wall() // 60)
        if minute != self._minute:
            self._minute = minute
            self._used = self.background_per_minute


class SimulatedSource(IBotReadRefresh):
    """The host's reads, with a true cost per scope; records every call and when it happened."""

    def __init__(
        self,
        venue: SimulatedVenue,
        bots: int,
        *,
        facts_cost: int = 20,
        planner_cost: int = 25,
        fills_cost: int = 30,
        static_cost: int = 5,
        candles_cost: int = 25,
    ) -> None:
        self.venue = venue
        self.cost = {
            "facts": facts_cost,
            "planner": planner_cost,
            "fills": fills_cost,
            "static": static_cost,
            "candles": candles_cost,
        }
        self.exposed = [f"bot{i:03d}" for i in range(bots)]
        self.at_rest: list[str] = []
        self.calls: list[tuple[float, str, str]] = []
        self.failing: dict[str, bool] = defaultdict(bool)

    def targets(self) -> tuple[RefreshTarget, ...]:
        rows = [(bot, True) for bot in self.exposed] + [
            (bot, False) for bot in self.at_rest
        ]
        return tuple(
            RefreshTarget(bot, VENUE, "BTCUSDT", exposure=exposed)
            for bot, exposed in sorted(rows)
        )

    def refresh(self, bot_id: str, scope: RefreshScope) -> RefreshOutcome:
        self.calls.append((self.venue.clock.seconds, bot_id, scope.value))
        self.venue.spend(
            self.cost[scope.value], ours=True, header=scope.value != "candles"
        )
        self.venue.clock.seconds += 1.0
        if self.failing[bot_id]:
            return RefreshOutcome(None, "the exchange's facts were not read")
        return RefreshOutcome(datetime(2026, 10, 27, tzinfo=UTC))

    def refresh_static(self, venue: TradingVenue) -> RefreshOutcome:
        self.calls.append((self.venue.clock.seconds, venue.value, "static"))
        self.venue.spend(self.cost["static"], ours=True)
        return RefreshOutcome(datetime(2026, 10, 27, tzinfo=UTC))

    def reads_of(self, scope: str) -> int:
        return sum(1 for _, _, s in self.calls if s == scope)


#: Asks the refresher to find the venue unmeasured.
NO_METER = object()


def refresher_for(
    source: SimulatedSource,
    settings: VpsFeedSettings | None = None,
    meter: object = None,
) -> FactsRefresher:
    clock = source.venue.clock
    return FactsRefresher(
        source,
        lambda _venue: None if meter is NO_METER else source.venue,
        settings or VpsFeedSettings.judged(120, 3.0, True),
        clock.monotonic,
        clock.wall,
    )


def drive(refresher: FactsRefresher, clock: SimulatedClock, seconds: float) -> None:
    """Run the worker's loop for `seconds` of simulated time."""
    end = clock.seconds + seconds
    while clock.seconds < end:
        asked = refresher.step()
        clock.seconds += max(asked, 0.01)
