"""How much exposure a ladder opens at start (`EPIC-039A`, DESIGN §5).

A value, declared now because the venue profile lists which directions a market allows; the
planner that uses all three is `EPIC-039B`. Spot allows `LONG` only.
"""

from __future__ import annotations

from enum import Enum


class TradeDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
