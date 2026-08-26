"""
@brief `StatCard` — a `Card` showing one headline figure.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..controls import Badge
from ..style import StyleRole, Tone, apply_role, tone_colour
from ..surface import Card


class StatCard(Card):
    """
    @brief A `Card` with a headline value, an optional unit suffix, an
    optional badge, and an optional caption line beneath.

    @details
    Covers both shapes the reference consumer hand-rolls: its metric cards
    (title + value + suffix + coloured badge, ×2 call sites) and its stat
    tiles (label + value + a small caption line, ×2 call sites). Neither
    needs the other's extras, so all three are optional and hidden when
    empty rather than split into two classes over what is one card with
    slots.

    The reference metric card's **hover lift** is reproduced (`STAT_CARD`),
    as QSS `:hover` rather than the consumer's `enterEvent`/`leaveEvent`
    pair — one declaration instead of two handlers that must be kept in
    sync, and it cannot get stuck in the hovered look if a leave event is
    missed.

    Two of its behaviours are still **not** reproduced:

    - Its always-drawn `info` icon. It has no tooltip and no click handler,
      so it carries no information — a decorative glyph. Reproducing it
      would mean every `StatCard` in every app grows an icon that does
      nothing.
    - Its value font shrinking past ten characters. A real usability fix,
      recorded in `EPIC-007B` as a candidate; it needs a rule about *when*
      to shrink, which is a layout decision this class has no basis to make
      for one caller.
    """

    def __init__(
        self,
        title: str,
        *,
        value: str = "",
        suffix: str = "",
        caption: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)
        # Re-applied over `Surface`'s own `SURFACE`: same chrome plus a
        # hover response. Done here rather than by `Surface` accepting a
        # role parameter, so the hover stays specific to this shape.
        apply_role(self, StyleRole.STAT_CARD)
        # The card's own title reads as a small muted heading over the
        # figure, which is exactly `SECTION_LABEL` — `Card` leaves its title
        # unstyled because a generic card has no opinion, but a stat card
        # does.
        #
        # Styling only: the text is left exactly as given. `SectionLabel`
        # uppercases itself and documents why, but doing that here would
        # make the inherited `Card.title` lossy — a caller could no longer
        # read back what it set. A label may redefine its own text; a
        # subclass quietly changing an inherited property's round-trip is a
        # different and worse surprise. A caller wanting uppercase passes
        # uppercase.
        apply_role(self._title_label, StyleRole.SECTION_LABEL)

        value_row = QHBoxLayout()
        self._value_label = QLabel(value)
        value_row.addWidget(self._value_label)

        self._suffix_label = QLabel(suffix)
        apply_role(self._suffix_label, StyleRole.CAPTION)
        self._suffix_label.setVisible(bool(suffix))
        value_row.addWidget(self._suffix_label)

        self._badge_label = Badge()
        value_row.addWidget(self._badge_label)

        value_row.addStretch(1)
        self.body_layout.addLayout(value_row)

        self._caption_label = QLabel(caption)
        apply_role(self._caption_label, StyleRole.CAPTION)
        self._caption_label.setVisible(bool(caption))
        self.body_layout.addWidget(self._caption_label)

        self.set_value(value)

    @property
    def value(self) -> str:
        return self._value_label.text()

    @property
    def caption(self) -> str:
        return self._caption_label.text()

    @property
    def badge_text(self) -> str:
        return self._badge_label.text()

    def set_value(self, value: str, *, tone: Tone = Tone.NEUTRAL) -> None:
        """@brief Sets the headline figure and how it should read."""
        self._value_label.setText(value)
        # Size and weight come from the role; only the colour is decided per
        # card. Appended as its own scoped rule rather than a bare property,
        # which `BUG-009` established is silently discarded by Qt once the
        # role's QSS carries a selector.
        apply_role(self._value_label, StyleRole.STAT_VALUE)
        selector = type(self._value_label).__name__
        self._value_label.setStyleSheet(
            f"{self._value_label.styleSheet()}"
            f"{selector} {{ color: {tone_colour(tone)}; }}"
        )

    def set_suffix(self, suffix: str) -> None:
        self._suffix_label.setText(suffix)
        self._suffix_label.setVisible(bool(suffix))

    def set_caption(self, caption: str) -> None:
        self._caption_label.setText(caption)
        self._caption_label.setVisible(bool(caption))

    def set_badge(self, text: str, *, tone: Tone = Tone.NEUTRAL) -> None:
        """@brief Sets the small pill beside the value, hiding it when
        `text` is empty — the same "empty means absent" contract the
        consumer's metric card already uses for its badge and suffix."""
        self._badge_label.setText(text)
        self._badge_label.setVisible(bool(text))
        if not text:
            return
        # Delegated to the badge rather than appending a `color:` here.
        # This method used to hand-roll that append, with a comment saying
        # it would break if `BADGE` ever grew a selector block. `BUG-008`
        # then gave every role a selector, and it did break: Qt discards a
        # bare property sitting after a closing brace, so the tone silently
        # stopped rendering while the string still ended in the right token.
        # `Badge.set_tone()` already emits a correctly scoped override.
        self._badge_label.set_tone(tone)
