"""`EPIC-021G` — the in-memory record of "is live trading on right now, and
what does this app currently believe about the account".

@details Deliberately **not** persisted, and deliberately **not** read
from `ConfigKeys.TRADING_ENABLED`'s saved value on boot — `EPIC-021G` §2.3
point 2 requires the user to turn trading on explicitly every session,
the one place in this app that intentionally does not follow `EPIC-010`'s
normal "remember what the user last set" convention. A fresh
`TradingSessionState` is always `enabled=False`; only `EnableTradingCommand`
(after it re-reconciles against the exchange) may flip it on.

`known_open_symbols` starts as whatever `EnableTradingCommand`'s
reconciliation found, and grows conservatively afterward:
`record_order_sent()` marks a symbol as "assume open" the moment an order
for it is sent, before this app has any confirmation it filled — safer to
over-block a second order on the same symbol than to under-block one,
pending `EPIC-021H`'s User Data Stream becoming the real source of truth
for whether it actually did.
"""

from __future__ import annotations

from datetime import datetime, timedelta


class TradingSessionState:
    """Plain mutable service, one instance per app process (a DI
    singleton) — deliberately not a frozen value object, since its whole
    job is to be mutated in place as orders go out."""

    def __init__(self) -> None:
        self.enabled = False
        self.orders_sent_this_session = 0
        self.known_open_symbols: set[str] = set()
        self._last_order_time_by_symbol: dict[str, datetime] = {}

    def enable(self, open_symbols: set[str]) -> None:
        """@brief Turns trading on for this session, seeded with
        `open_symbols` from a just-completed reconciliation."""
        self.enabled = True
        self.known_open_symbols = set(open_symbols)

    def disable(self) -> None:
        self.enabled = False

    def open_position_count(self, symbol: str) -> int:
        """@brief One-way mode (assumed throughout this epic) means a
        symbol is either flat (0) or has exactly one open position (1) —
        never a real count, but shaped as one so `TradingLimitContext`
        stays generalizable if that assumption ever needs to loosen."""
        return 1 if symbol in self.known_open_symbols else 0

    def time_since_last_order(self, symbol: str, now: datetime) -> timedelta | None:
        last = self._last_order_time_by_symbol.get(symbol)
        return None if last is None else now - last

    def record_order_sent(self, symbol: str, when: datetime) -> None:
        self.orders_sent_this_session += 1
        self._last_order_time_by_symbol[symbol] = when
        self.known_open_symbols.add(symbol)
