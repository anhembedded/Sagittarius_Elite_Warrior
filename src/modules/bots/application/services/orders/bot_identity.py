"""`EPIC-029E` — who one bot is to trading.

Split from `bot_order_gateway.py` (the 400-line ceiling) so the readers and the request
builders the gateway uses can name it without importing the gateway. The gateway re-exports
`BotIdentity`, so the importers that named it there are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BotIdentity:
    """Who the bot is to trading: its owner id, its tag, the symbol it trades."""

    owner_id: str
    tag: str
    symbol: str
