"""`EPIC-029C` — the report's advisory thresholds, as editable defaults (PRO-006 §1.5, §4.2).

Each number is advice, not a rule: crossing it is a WARNING with the measured
value beside it. They are a value the kind is built with, so a user setting can
replace any of them without a code change; nothing here is read from a
constant inside a check.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class FuturesGridThresholds:
    """`EPIC-039G`, `EPIC-039F` - the advisory numbers only a position venue has (DESIGN §6).
    Like the Spot ones, a value the kind is built with, never a literal inside a check."""

    #: A plan's funding costs more than this share of its expected cycle profit per
    #: funding interval: `FUNDING_ADVERSE`.
    funding_adverse_share: Decimal = Decimal("0.25")
    #: The stop loss should sit at least this many daily ATRs before the liquidation
    #: price (`EPIC-029K`); nearer is a WARNING.
    min_liq_buffer_atr: Decimal = Decimal(1)
    #: A stop loss nearer the estimated liquidation than this share of its own price is REFUSED
    #: (`BUG-255`), with or without a daily ATR: a gap through a stop that close would leave only
    #: the liquidation. The ATR buffer above stays an advisory.
    min_liq_gap_ratio: Decimal = Decimal("0.005")
    #: Leverage above this is a WARNING (decision O4).
    leverage_warn: int = 10
    #: Leverage above this is REFUSED, whatever the bracket allows (decision O4).
    leverage_ceiling: int = 20
    #: A running bot is WARN when the exchange's liquidation price is within this
    #: fraction of the mark price, CRITICAL within `liq_critical_distance` (owner's
    #: numbers; the defaults are the guard author's recommendation, see the task).
    liq_warn_distance: Decimal = Decimal("0.05")
    liq_critical_distance: Decimal = Decimal("0.02")
    #: Back to SAFE only past `liq_warn_distance x` this, so a mark hovering on the line
    #: raises one event, not a stream.
    liq_rearm_factor: Decimal = Decimal("1.1")
    #: A snapshot older than this says nothing about now: UNKNOWN, never SAFE.
    risk_snapshot_max_age: timedelta = timedelta(seconds=60)
    #: A bot that cannot judge its liquidation distance (the state is UNKNOWN, or no
    #: reading ever arrived) for longer than this while it may hold a position halts (the
    #: owner's rule, 2026-10-13).
    risk_unknown_halt_after: timedelta = timedelta(seconds=120)
    #: How long the bot waits before it re-reads a position that moved with no order of its
    #: own, so the user-data stream has time to deliver the matching fill first.
    position_recheck_delay: timedelta = timedelta(seconds=5)

    def __post_init__(self) -> None:
        if not 0 < self.liq_critical_distance < self.liq_warn_distance < 1:
            raise ValueError(
                "liquidation distances need 0 < critical < warn < 1, got "
                f"{self.liq_critical_distance} and {self.liq_warn_distance}"
            )
        if self.liq_rearm_factor < 1:
            raise ValueError("liq_rearm_factor must be at least 1")
        if not 1 <= self.leverage_warn <= self.leverage_ceiling:
            raise ValueError("leverage thresholds need 1 <= warn <= ceiling")
        if self.min_liq_buffer_atr < 0:
            raise ValueError("min_liq_buffer_atr must not be negative")
        if not 0 <= self.min_liq_gap_ratio < 1:
            raise ValueError("min_liq_gap_ratio must be at least 0 and below 1")
        if self.risk_snapshot_max_age <= timedelta(0):
            raise ValueError("risk_snapshot_max_age must be positive")
        if self.risk_unknown_halt_after <= timedelta(0):
            raise ValueError("risk_unknown_halt_after must be positive")
        if self.position_recheck_delay < timedelta(0):
            raise ValueError("position_recheck_delay must not be negative")


@dataclass(frozen=True, slots=True)
class GridThresholds:
    """The defaults behind every Grid warning."""

    #: The report: at least 0.5% per step, to leave room for slippage.
    min_step_fraction: Decimal = Decimal("0.005")
    #: The report: a range of about 2–4 × the daily ATR(14).
    range_atr_low: Decimal = Decimal(2)
    range_atr_high: Decimal = Decimal(4)
    #: The report: stop loss 3–8% below the lower limit, take profit 3–8% above the upper.
    exit_distance_low: Decimal = Decimal("0.03")
    exit_distance_high: Decimal = Decimal("0.08")
    #: The report: arithmetic and geometric diverge beyond a range of about 20%.
    arithmetic_max_range_fraction: Decimal = Decimal("0.20")
    #: `EPIC-039G` — what only a position venue judges.
    futures: FuturesGridThresholds = FuturesGridThresholds()
