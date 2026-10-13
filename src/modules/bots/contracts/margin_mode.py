"""Which margin a position is held on (`EPIC-039A`, decision O5).

Futures offers `ISOLATED` in this epic; `CROSS` needs the other positions' maintenance margin
and is an extension case (DESIGN §11). Spot has no margin mode.
"""

from __future__ import annotations

from enum import Enum


class MarginMode(str, Enum):
    ISOLATED = "isolated"
    CROSS = "cross"
