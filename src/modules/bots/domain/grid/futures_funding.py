"""`EPIC-039K` — the funding a Futures replay charges, as the bots module's own values.

@details A replay is pure: the application hands it the settlements the exchange recorded
(`IFundingHistory`, `market_data`) and a `FundingCharger` that turns one into money. The
arithmetic is `ICostModel.funding_estimate` (`EPIC-039G`) fed with the settlement's own rate;
this module only names what crosses the seam.

@par What a settlement charges
The held position's signed quantity times the settlement's mark price times its rate:
positive means the position pays, negative that it earns (a long pays a positive rate, a
short a negative one). A record without a mark price (the field exists from 2023-11-01) is
charged at the price the replay last saw, and `FundingSchedule.note` says so.

@par When it is charged
The position held at the settlement instant pays; a settlement at or before the first
candle's open charges nothing, because the position opens there. A coarse candle (no
1-second klines) holds its settlements until its end, so they charge the position the candle
left. Both are the replay's reading of candles, not the exchange's clock.

@par Extension cases
  · a symbol with another interval - nothing changes: each settlement carries its own rate
    for its own interval;
  · cross margin - the charger is unchanged; the margin the funding comes out of is the
    liquidation module's;
  · a funding history from a file - another producer of `FundingSchedule`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class FundingSettlement:
    """One recorded settlement."""

    time: datetime
    #: A fraction of the position's notional; positive means longs pay shorts.
    rate: Decimal
    #: The mark price the exchange charged on; `None` for a record that predates the field.
    mark_price: Decimal | None


@dataclass(frozen=True, slots=True)
class FundingSchedule:
    """The settlements a replay charges, oldest first, and whether funding is in the result.

    `included` is `False` when the history could not be read and the caller chose to replay
    without it (`FundingRequirement.OPTIONAL`): the result then says so, prominently, because
    a leveraged grid's profit without funding is flattered."""

    settlements: tuple[FundingSettlement, ...]
    included: bool
    #: One sentence for the result: how many settlements, which price, or why none.
    note: str

    def __post_init__(self) -> None:
        if not self.included and self.settlements:
            raise ValueError("a schedule without funding holds no settlements")
        if any(
            later.time < earlier.time
            for earlier, later in zip(
                self.settlements, self.settlements[1:], strict=False
            )
        ):
            raise ValueError("settlements are oldest first")


#: `(position, mark price, rate) -> charge`: positive when the position pays, negative when it
#: earns. The application supplies it from `ICostModel.funding_estimate`.
type FundingCharger = Callable[[Decimal, Decimal, Decimal], Decimal]


def no_funding(note: str) -> FundingSchedule:
    """A schedule for a replay that runs without funding, saying why."""
    return FundingSchedule((), False, note)


class SettlementCursor:
    """The settlements of a schedule, handed out once each as they fall due."""

    def __init__(self, schedule: FundingSchedule, after: datetime) -> None:
        self._pending = [s for s in schedule.settlements if s.time > after]
        self._next = 0

    def next_due(self, until: datetime) -> FundingSettlement | None:
        """The next settlement at or before `until`, consumed; `None` when none is due."""
        if self._next < len(self._pending) and self._pending[self._next].time <= until:
            self._next += 1
            return self._pending[self._next - 1]
        return None
