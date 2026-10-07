"""`EPIC-034` D3, D11 — the one confirmation that names real money.

@details A mainnet venue trades exactly like a testnet one (D11: no order is
blocked), with one exception the owner kept: the first Start, arm or order on a
mainnet venue in a session asks once, in words that say the account is real. An
order is a manual order and a Close position (a market order); Emergency stop and
cancelling only reduce what the account is exposed to and are never asked.
It is a question, not a block: the answer "use real money" is remembered for that
venue until the app closes, and a testnet venue is never asked. Declining sends
nothing.

Asked from the UI thread, before the action that places orders begins: the bots
screen before Start and Arm, the order desk before a manual order's own
confirmation, the account tabs before a close. The screens ask, not the order
path, so the one venue a screenless caller acts on is never a mainnet
(`TradingVenue` order; `test_resolve_trading_venues.py`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class IRealMoneyConsent(ABC):
    @abstractmethod
    def confirmed(self, venue: TradingVenue, action: str) -> bool:
        """`True` when `action` may go on at `venue`: it is a testnet, or this
        session already agreed to real money there, or the person agrees now.
        @param action What is about to happen, in the person's words
        ("start this bot", "arm a strategy", "place an order")."""
