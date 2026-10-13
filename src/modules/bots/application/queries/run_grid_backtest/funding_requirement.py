"""`EPIC-039K` — what a Futures backtest does when the funding history cannot be read."""

from __future__ import annotations

from enum import Enum


class FundingRequirement(str, Enum):
    """Decision O9 puts funding in a Futures backtest, because a replay that ignores it flatters
    a leveraged grid. When the history cannot be read the choice is the caller's, and the
    default refuses."""

    #: Refuse, saying why: no figure is shown that omits funding unannounced.
    REQUIRED = "required"
    #: Replay without funding and say so in the result (`FuturesOutcome.funding_included`),
    #: which the screen must show next to every figure. For a user who asked for it.
    OPTIONAL = "optional"
