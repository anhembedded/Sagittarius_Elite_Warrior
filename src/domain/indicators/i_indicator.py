from abc import ABC, abstractmethod


class IIndicator[T_co](ABC):
    """
    @brief Contract for a stateful, streaming technical indicator.
    @details Implementations hold their own state between calls so the exact
    same `update()` path serves both batch (replay from a fresh instance) and
    incremental (long-lived instance fed one value at a time) usage — this is
    what guarantees the two modes can never produce different results.

    `ABC`, not `Protocol` (`architecture-rule.md` §2.1 default): every
    concrete indicator (`EMA`, `MACD`, `RSI`, `WMA`, `SupportResistance`)
    already inherits `IIndicator[...]` nominally — nothing relies on
    structural typing here.
    """

    @abstractmethod
    def update(self, value: float) -> T_co | None:
        """
        @param value The latest input (e.g. a candle's close price).
        @returns The indicator's current reading, or None while still warming up.
        """

    @abstractmethod
    def peek_provisional(self, value: float) -> T_co | None:
        """
        @brief Tentative reading for a bar still forming — never mutates state.
        @details Computes the exact same formula `update()` would, from the
        already-committed state plus `value`, without writing anything back.
        Safe to call any number of times per bar (a tick stream); the next
        `update()` call is unaffected by how many times this was called, or
        with what values. Returns None under the same warm-up condition as
        `update()` (BOT-042B).
        """
