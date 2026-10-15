"""`BUG-216` - the symbols whose position re-read the exchange's pause kept from being read.

An `ACCOUNT_UPDATE` names the symbols whose position changed, and the stream reads each one back
through the venue's gated client. While the exchange's pause runs that read is refused at once;
the symbol is kept here and read with the next update's, in the order the pauses met them, each
once. Touched only on the stream's event loop, so it holds no lock.
"""

from __future__ import annotations

from collections.abc import Iterable


class DeferredRereads:
    """Symbols waiting for a position re-read, in the order they were deferred."""

    def __init__(self) -> None:
        self._symbols: dict[str, None] = {}

    def defer(self, symbol: str) -> None:
        self._symbols[symbol] = None

    def due_with(self, changed: Iterable[str]) -> list[str]:
        """The deferred symbols, then the ones `changed` adds, each once; the deferred are
        taken out."""
        due = list(dict.fromkeys([*self._symbols, *changed]))
        self._symbols = {}
        return due

    def clear(self) -> None:
        self._symbols = {}
