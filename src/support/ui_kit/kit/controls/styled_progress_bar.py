"""
@brief `StyledProgressBar` — a `QProgressBar` rendered from tokens.
"""

from __future__ import annotations

from PySide6.QtWidgets import QProgressBar, QWidget

from ..style import StyleRole, WidgetState, apply_role

#: Qt's own convention for "busy, total unknown": an equal minimum and
#: maximum makes the chunk sweep instead of filling. Named so the call sites
#: below do not read as an off-by-one.
_INDETERMINATE_RANGE = (0, 0)

#: What a bar falls back to when asked to leave indeterminate mode without
#: ever having had a real range. Qt's own default, restated because the
#: restore path has to pick something.
_DEFAULT_RANGE = (0, 100)


class StyledProgressBar(QProgressBar):
    """
    @brief A `QProgressBar` styled through `apply_role()`, with an
    indeterminate mode that remembers the range it came from.

    @details
    **This is the bar, not the reference consumer's whole progress widget.**
    That one is a `QWidget` holding a muted caption *above* a bar, and all
    three of its call sites use only the caption — none ever calls
    `set_value` or `set_range`. The caption is a `CAPTION`-roled label, so
    a consumer composes the two rather than this class growing a label it
    cannot lay out for them. The composite is recorded in `EPIC-007C` as a
    candidate; it has one instance, and its shape is a column, which makes
    it a surface rather than a leaf control.

    **Leaving indeterminate mode restores the previous range.** The
    consumer's version makes `set_indeterminate(False)` a deliberate no-op,
    with a comment explaining that clearing busy mode would otherwise
    clobber a range set separately. Remembering the range removes the reason
    for that no-op: turning the mode off puts back exactly what was there,
    so callers no longer have to re-issue `setRange` and no longer silently
    stay busy if they forget.

    **The percentage is hidden by default.** The consumer sets
    `setTextVisible(True)` on a bar it also fixes to 10px tall, with a 10px
    font and a 1px border — text that cannot fit. Nobody has noticed because
    nothing in that app ever sets a value. Rather than port the setting by
    reflex, this leaves it off; a caller with a bar tall enough to read
    turns it on.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._restore_range: tuple[int, int] = _DEFAULT_RANGE
        self.setTextVisible(False)
        apply_role(self, StyleRole.PROGRESS)

    @property
    def indeterminate(self) -> bool:
        return (self.minimum(), self.maximum()) == _INDETERMINATE_RANGE

    def set_indeterminate(self, indeterminate: bool) -> None:
        """@brief Switches between a sweeping busy bar and a measured one,
        restoring the range the bar had before it went busy."""
        if indeterminate:
            if not self.indeterminate:
                self._restore_range = (self.minimum(), self.maximum())
            self.setRange(*_INDETERMINATE_RANGE)
            return
        if self.indeterminate:
            self.setRange(*self._restore_range)

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        # Same reason `StyledButton` does this: QSS is a static string, so
        # the disabled variant has to be re-rendered rather than left to
        # Qt's `:disabled` pseudo-state, which this role's block overrides.
        apply_role(
            self,
            StyleRole.PROGRESS,
            state=WidgetState.NORMAL if enabled else WidgetState.DISABLED,
        )
