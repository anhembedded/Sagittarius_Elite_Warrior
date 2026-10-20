"""`EPIC-039L` (criterion 9) - what a halt that cannot close says about the protective stop.

@details A switch-off, a rejected key or a rate limit halts a Futures bot without a cancel or a
close, so its position stays open on the exchange. The one thing that protects it meanwhile is the
stop, and the halt's words say whether it stands, read from the exchange, never from the bot's own
record alone: the record can say a stop stands that was cancelled by hand.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop import (
    ProtectiveStop,
)


class StopFinding(Enum):
    """What the record and the exchange together say about the stop over a position."""

    UNREAD = "unread"
    NONE_RECORDED = "none recorded"
    NOT_ON_EXCHANGE = "not on the exchange"
    DOES_NOT_COVER = "does not cover"
    STANDS = "stands"


_WORDS = {
    StopFinding.UNREAD: "whether its protective stop stands could not be read",
    StopFinding.NONE_RECORDED: "no protective stop stands over it",
    StopFinding.NOT_ON_EXCHANGE: "its protective stop is not on the exchange",
    StopFinding.DOES_NOT_COVER: (
        "its protective stop stands but does not cover the position"
    ),
    StopFinding.STANDS: "its protective stop stands on the exchange",
}


def judge_stop(
    recorded: Iterable[ProtectiveStop], on_exchange: set[str] | None, covering: set[str]
) -> StopFinding:
    """@param recorded The stops the bot's record holds.
    @param on_exchange The client ids of the bot's protective stops open on the exchange, or `None`
    when the exchange or the position could not be read.
    @param covering The client ids of the stops whose side closes the position as it is now."""
    stops = tuple(recorded)
    if on_exchange is None:
        return StopFinding.UNREAD
    if not stops:
        return StopFinding.NONE_RECORDED
    if not all(stop.client_order_id in on_exchange for stop in stops):
        return StopFinding.NOT_ON_EXCHANGE
    if not on_exchange & covering:
        return StopFinding.DOES_NOT_COVER
    return StopFinding.STANDS


def stop_words(
    recorded: Iterable[ProtectiveStop], on_exchange: set[str] | None, covering: set[str]
) -> str:
    """The halt's sentence for `judge_stop`'s finding (same parameters)."""
    return words_of(judge_stop(recorded, on_exchange, covering))


def words_of(finding: StopFinding) -> str:
    return _WORDS[finding]
