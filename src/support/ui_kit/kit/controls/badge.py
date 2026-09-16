"""
@brief `Badge` — a small pill carrying a count or a short status word.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from ..style import StyleRole, Tone, WidgetState, tone_colour
from .styled_label import StyledLabel


class Badge(StyledLabel):
    """
    @brief A `StyledLabel` rendered as a small chip — the shape that sits
    beside a title to say how many, or beside a value to say how it
    compares.

    @details
    Covers the reference consumer's seven hand-rolled badges through two
    entry points, because they turned out to answer two different
    questions:

    - **Chrome badges** (a log panel's entry count, a tab's count, a data
      row's interval chip) carry fixed palette colours and, at most, an
      idle-versus-current pair. That is `emphasised`, and it is exactly what
      `StyleRole.BADGE` already renders.
    - **Semantic badges** (long versus short, profit versus loss, a metric's
      delta) look at first like they need an arbitrary runtime colour — the
      consumer passes literal greens and reds, and derives their background
      with an alpha helper. They do not: every one is really asking positive
      / negative / neutral, so `set_tone()` answers it from tokens. Handing
      this class a hex instead would push the app straight back to calling
      `setStyleSheet` itself, which `guards.find_inline_stylesheets` exists
      to reject.

    Hides itself when its text is empty rather than rendering an empty chip.

    **No fixed height.** The seven instances use 18, 20, 22, 24 and three
    with none at all; baking one in would be picking a winner among callers
    with no reason to. Height comes from the text plus the role's padding,
    or from whatever the caller sets.

    One shape is deliberately **not** covered: the dev board's connection
    badge is a `QFrame` holding a status dot beside its label. Giving this
    class an optional child dot would turn a label into a container.
    Recorded in `EPIC-007C` as a candidate.
    """

    def __init__(
        self,
        text: str = "",
        *,
        emphasised: bool = False,
        tone: Tone | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, role=StyleRole.BADGE, parent=parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tone: Tone | None = None
        self.setVisible(bool(text))
        self.set_emphasised(emphasised)
        if tone is not None:
            self.set_tone(tone)

    @property
    def emphasised(self) -> bool:
        return self.state is WidgetState.SELECTED

    @property
    def tone(self) -> Tone | None:
        """The semantic tone in force, or `None` while the badge is rendering
        plain chrome."""
        return self._tone

    def set_emphasised(self, emphasised: bool) -> None:
        """@brief Switches between the idle and current forms — a tab's
        count while that tab is open. Named on the badge rather than
        exposing `WidgetState.SELECTED`, because "selected" describes the
        tab, not the number printed on it."""
        self._tone = None
        self.set_state(WidgetState.SELECTED if emphasised else WidgetState.NORMAL)

    def set_tone(self, tone: Tone) -> None:
        """@brief Recolours the badge to read as positive, negative or
        neutral. Mutually exclusive with `emphasised` — a chip is either
        chrome or a verdict, and the consumer has no instance that is
        both."""
        self._tone = tone
        self.set_state(WidgetState.NORMAL)
        # Appended after the role's own scoped block, relying on
        # last-declaration-wins, the same way `StatCard`'s badge tone does.
        # `apply_role()` (BUG-008 fix) now scopes `BADGE`'s QSS to this
        # widget's own type selector, so the override must use that same
        # selector rather than a bare property — a bare property here would
        # dangle after the role block's closing `}` and never apply. A test
        # pins that the tone actually reaches the rendered QSS.
        selector = type(self).__name__
        self.setStyleSheet(
            f"{self.styleSheet()}{selector} {{ color: {tone_colour(tone)}; }}"
        )

    def setText(self, text: str) -> None:
        """@brief Sets the text and hides the pill when it is empty.

        @details Overrides `QLabel.setText` rather than adding a `set_text`
        beside it: a consumer holding this as a `QLabel` — and several will,
        since that is what it is — would otherwise bypass the hiding rule
        without knowing it existed."""
        super().setText(text)
        self.setVisible(bool(text))
