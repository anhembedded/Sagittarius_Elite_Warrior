"""`BUG-211` — the one INFO line a suggestion applied leaves in the log.

Apart from `grid_panel.py` (the widgets): it is the record that lets a plan the owner did not
type be traced to its source, its inputs, the range written, the exits moved and how the plan
then reads (`logging-rule.md` §2).
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
    SuggestedRange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_advice import plain
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_suggestion import (
    PlanSuggestion,
)

logger = logging.getLogger("App.Bots.Grid")


def log_suggestion(
    suggestion: PlanSuggestion, band: SuggestedRange, market: PlannerMarket
) -> None:
    view, terms = market.market, market.terms
    if view is None or terms is None:
        return
    daily_atr = "n/a" if view.daily_atr is None else plain(view.daily_atr)
    logger.info(
        "[grid-suggest] source=%s band=%s-%s daily_atr=%s last_price=%s tick=%s "
        "range=%s-%s exits_moved=%s blocking=%d%s",
        suggestion.source,
        plain(band.lower),
        plain(band.upper),
        daily_atr,
        plain(view.last_price),
        plain(terms.tick_size),
        plain(suggestion.lower),
        plain(suggestion.upper),
        suggestion.log_moves,
        len(suggestion.blocking),
        f" ({', '.join(suggestion.blocking)})" if suggestion.blocking else "",
    )
