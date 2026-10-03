"""`EPIC-029C` — the report's advisory thresholds, as editable defaults (PRO-006 §1.5, §4.2).

Each number is advice, not a rule: crossing it is a WARNING with the measured
value beside it. They are a value the kind is built with, so a user setting can
replace any of them without a code change; nothing here is read from a
constant inside a check.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


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
