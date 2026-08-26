"""Tests for `StyledLabel`, `SectionLabel` and `Badge` (EPIC-007C)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Badge,
    SectionLabel,
    StyledLabel,
    StyleRole,
    Tone,
    WidgetState,
)

# ---------------------------------------------------------------------- #
# StyledLabel
# ---------------------------------------------------------------------- #


def test_styled_label_is_abstract(qtbot):
    with pytest.raises(TypeError, match="StyledLabel is abstract"):
        StyledLabel("x", role=StyleRole.BADGE)


def test_subclasses_are_qlabels(qtbot):
    for widget in (SectionLabel("heading"), Badge("1")):
        qtbot.addWidget(widget)
        assert isinstance(widget, QLabel)
        assert isinstance(widget, StyledLabel)


def test_set_state_rerenders(qtbot, fake_theme_bridge):
    """The one behaviour that justifies this base existing at all — both
    subclasses re-render after construction, in a state that changes at
    runtime."""
    badge = Badge("7")
    qtbot.addWidget(badge)
    before = badge.styleSheet()

    badge.set_state(WidgetState.SELECTED)

    assert badge.state is WidgetState.SELECTED
    assert badge.styleSheet() != before


# ---------------------------------------------------------------------- #
# SectionLabel
# ---------------------------------------------------------------------- #


def test_section_label_uppercases(qtbot):
    """The consumer is inconsistent: one helper calls `.upper()` and is
    passed Title Case, two others are handed already-uppercase strings."""
    label = SectionLabel("System Controls")
    qtbot.addWidget(label)

    assert label.text() == "SYSTEM CONTROLS"


def test_section_label_uppercases_on_set_text_too(qtbot):
    label = SectionLabel("first")
    qtbot.addWidget(label)

    label.setText("Data Range")

    assert label.text() == "DATA RANGE"


def test_uppercasing_is_idempotent_for_already_uppercase_callers(qtbot):
    label = SectionLabel("TARGET & TIMEFRAME")
    qtbot.addWidget(label)

    assert label.text() == "TARGET & TIMEFRAME"


def test_tick_is_off_by_default(qtbot):
    """Only one of the consumer's three headings has the accent tick.
    Defaulting it on would give the other two a visual element they never
    had."""
    label = SectionLabel("heading")
    qtbot.addWidget(label)

    assert label.tick is False
    assert label.role is StyleRole.SECTION_LABEL


def test_tick_uses_its_own_role_and_renders_a_border(qtbot, fake_theme_bridge):
    plain = SectionLabel("heading")
    qtbot.addWidget(plain)
    ticked = SectionLabel("heading", tick=True)
    qtbot.addWidget(ticked)

    assert ticked.role is StyleRole.SECTION_LABEL_TICKED
    assert "border-left" in ticked.styleSheet()
    assert "border-left" not in plain.styleSheet()
    assert "<accent>" in ticked.styleSheet()


# ---------------------------------------------------------------------- #
# Badge
# ---------------------------------------------------------------------- #


def test_badge_hides_itself_when_empty(qtbot):
    empty = Badge()
    qtbot.addWidget(empty)
    filled = Badge("340 EVENTS")
    qtbot.addWidget(filled)

    assert empty.isVisibleTo(empty) is False
    assert filled.isVisibleTo(filled) is True


def test_setting_empty_text_hides_it_again(qtbot):
    badge = Badge("12")
    qtbot.addWidget(badge)

    badge.setText("")

    assert badge.isVisibleTo(badge) is False


def test_emphasised_renders_differently(qtbot, fake_theme_bridge):
    idle = Badge("12")
    qtbot.addWidget(idle)
    current = Badge("12", emphasised=True)
    qtbot.addWidget(current)

    assert current.emphasised is True
    assert idle.emphasised is False
    assert idle.styleSheet() != current.styleSheet()


@pytest.mark.parametrize(
    ("tone", "token"),
    [
        (Tone.POSITIVE, "<success>"),
        (Tone.NEGATIVE, "<danger>"),
        (Tone.NEUTRAL, "<textPrimary>"),
    ],
)
def test_tone_reaches_the_rendered_qss(qtbot, fake_theme_bridge, tone, token):
    """The consumer's long/short, profit/loss and delta badges each pass a
    literal green or red. Every one is really this question."""
    badge = Badge("LONG")
    qtbot.addWidget(badge)

    badge.set_tone(tone)

    assert f"color: {token};" in badge.styleSheet()


def test_tone_and_emphasis_are_mutually_exclusive(qtbot, fake_theme_bridge):
    """A chip is either chrome or a verdict — the consumer has no instance
    that is both, and letting them stack would leave the last caller to
    write winning silently."""
    badge = Badge("+4.2%", emphasised=True)
    qtbot.addWidget(badge)

    badge.set_tone(Tone.POSITIVE)
    assert badge.emphasised is False
    assert badge.tone is Tone.POSITIVE

    badge.set_emphasised(True)
    assert badge.tone is None


def test_badge_has_no_baked_in_height(qtbot):
    """The seven instances use 18, 20, 22, 24 and three with none — baking
    one in would be picking a winner among callers with no reason to."""
    badge = Badge("12")
    qtbot.addWidget(badge)

    assert badge.minimumHeight() == 0
    assert badge.maximumHeight() > 1000
