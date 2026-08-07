from typing import Protocol, TypeVar

T = TypeVar("T", covariant=True)


class IIndicator(Protocol[T]):
    """
    @brief Contract for a stateful, streaming technical indicator.
    @details Implementations hold their own state between calls so the exact
    same `update()` path serves both batch (replay from a fresh instance) and
    incremental (long-lived instance fed one value at a time) usage — this is
    what guarantees the two modes can never produce different results.
    """

    def update(self, value: float) -> T | None:
        """
        @param value The latest input (e.g. a candle's close price).
        @returns The indicator's current reading, or None while still warming up.
        """
        ...
