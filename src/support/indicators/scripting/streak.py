class Streak:
    """
    @brief Counts consecutive bars a condition has held true, resetting to 0
    the instant it doesn't.

    @details
    Formalises a pattern scripts otherwise hand-roll with a plain instance
    counter (Pine's `var int consecutiveBars` idiom): increment while a
    condition holds, snap back to 0 the moment it stops. Not a strict gap —
    a script can always do this with `self.n = 0` in `setup()` — but common
    enough (trend confirmation after N bars, "have we been overbought for the
    last 5 bars") that it earns a small reusable primitive, the same way
    `Series`/`crossed_above` did.

    Lives in `domain/scripting/` rather than `indicator_scripts/` for the
    same reason `Series` does: a future strategy script counting consecutive
    bars is exactly as legitimate a use as an indicator script doing it.
    """

    def __init__(self) -> None:
        self._count = 0

    def update(self, condition: bool) -> int:
        """Advances by one bar and returns the streak length after this bar."""
        self._count = self._count + 1 if condition else 0
        return self._count

    @property
    def current(self) -> int:
        return self._count
