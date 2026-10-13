"""`EPIC-039F` - how far a running position is from the exchange's liquidation price.

@details Pure. The distance is measured on the **mark** price, because Binance liquidates on
mark: `|mark - liquidation| / mark`, and a mark that has already passed the liquidation price
is distance zero. Both thresholds are `FuturesGridThresholds`' (the owner's numbers).

  · flat -> SAFE (nothing to liquidate);
  · a snapshot older than `risk_snapshot_max_age` -> UNKNOWN;
  · a position with no reported liquidation price -> UNKNOWN (the exchange said nothing; that
    is not "no risk");
  · distance below `liq_critical_distance` -> CRITICAL; below `liq_warn_distance` -> WARN.

**Hysteresis.** A bot already WARN stays WARN until the distance is back above
`liq_warn_distance x liq_rearm_factor`, so a mark hovering on the line is one WARN, not many.
CRITICAL has no hysteresis: it halts the bot, and nothing is judged after.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import (
    RiskLevel,
    RiskSnapshot,
    RiskState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)


def liquidation_distance(snapshot: RiskSnapshot) -> Decimal | None:
    """@return |mark - liquidation| / mark, zero once the mark has passed the liquidation
    price; `None` when the exchange reported no price or the position is flat."""
    liquidation = snapshot.liquidation_price
    if liquidation is None or snapshot.position == 0:
        return None
    mark = snapshot.mark_price
    passed = mark <= liquidation if snapshot.position > 0 else mark >= liquidation
    return Decimal(0) if passed else abs(mark - liquidation) / mark


def classify_risk(
    snapshot: RiskSnapshot,
    now: datetime,
    previous: RiskLevel,
    thresholds: FuturesGridThresholds,
) -> RiskState:
    """@return The state `snapshot` puts the bot in, judged at `now`."""
    age = now - snapshot.taken_at
    if age > thresholds.risk_snapshot_max_age:
        return RiskState(
            RiskLevel.UNKNOWN,
            f"The exchange's position was last read {age.total_seconds():.0f} s ago; "
            f"the limit is {thresholds.risk_snapshot_max_age.total_seconds():.0f} s",
        )
    if snapshot.position == 0:
        return RiskState(
            RiskLevel.SAFE, "No position stands; nothing can be liquidated"
        )
    distance = liquidation_distance(snapshot)
    if distance is None:
        return RiskState(
            RiskLevel.UNKNOWN,
            "The exchange reports a position but no liquidation price for it",
        )
    words = (
        f"The mark price {snapshot.mark_price} is {distance:.2%} from the exchange's "
        f"liquidation price {snapshot.liquidation_price}"
    )
    if distance < thresholds.liq_critical_distance:
        return RiskState(
            RiskLevel.CRITICAL,
            f"{words}, inside the critical {thresholds.liq_critical_distance:.2%}",
            distance,
        )
    warn = thresholds.liq_warn_distance
    if previous in (RiskLevel.WARN, RiskLevel.CRITICAL):
        warn *= thresholds.liq_rearm_factor
    if distance < warn:
        return RiskState(
            RiskLevel.WARN,
            f"{words}, inside the warning {thresholds.liq_warn_distance:.2%}",
            distance,
        )
    return RiskState(RiskLevel.SAFE, words, distance)
