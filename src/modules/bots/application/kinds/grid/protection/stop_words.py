"""`EPIC-039L` (criterion 9) - what a halt that cannot close says about the protective stop.

@details A switch-off, a rejected key or a rate limit halts a Futures bot without a cancel or a
close, so its position stays open on the exchange. The one thing that protects it meanwhile is the
stop, and the halt's words say whether it stands, read from the exchange, never from the bot's own
record alone: the record can say a stop stands that was cancelled by hand.
"""

from __future__ import annotations

from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop import (
    ProtectiveStop,
)


def stop_words(recorded: Iterable[ProtectiveStop], on_exchange: set[str] | None) -> str:
    """@param recorded The stops the bot's record holds.
    @param on_exchange The client ids of the bot's protective stops open on the exchange, or `None`
    when the exchange could not be read."""
    stops = tuple(recorded)
    if on_exchange is None:
        return "whether its protective stop stands could not be read"
    if not stops:
        return "no protective stop stands over it"
    if all(stop.client_order_id in on_exchange for stop in stops):
        return "its protective stop stands on the exchange"
    return "its protective stop is not on the exchange"
