"""`EPIC-028O` — whether a stop-limit's stop price waits for the market."""

from __future__ import annotations

from enum import Enum


class StopPriceCheck(str, Enum):
    """@brief The verdict `stop_trigger_side.check_stop_trigger_side` gives
    and `OrderPreview.stop_check` carries."""

    #: A buy stop above the last price, or a sell stop below it.
    ON_TRIGGER_SIDE = "on_trigger_side"
    #: Already crossed: the exchange would reject it or trigger it at once.
    WRONG_SIDE = "wrong_side"
