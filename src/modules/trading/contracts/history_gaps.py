"""`EPIC-028Q` — what a venue's history cannot show, said in words a desk
can display.

@details Binance's history endpoints have limits no reader can work around:
Futures drops cancelled or expired orders with no fill after 3 days, and no
Spot endpoint lists the pairs an account traded. A reader states its venue's
limits here instead of answering as if the history were complete; the
history queries copy them onto `HistoryPage.notices` (the PR #300 epic
review, §3 items 1 and 2).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HistoryGaps:
    """One venue's known gaps, each a sentence a desk can show."""

    #: What an order history of one pair leaves out.
    order_history: tuple[str, ...] = ()
    #: What a history of "every pair" can miss beyond that.
    every_symbol: tuple[str, ...] = ()
