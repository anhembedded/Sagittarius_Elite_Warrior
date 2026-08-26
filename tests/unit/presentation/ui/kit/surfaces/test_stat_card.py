"""Tests for `widgets.surfaces.stat_card.StatCard`."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Card, StatCard, Tone


def test_is_a_card_carrying_its_title(qtbot):
    card = StatCard("Net Profit")
    qtbot.addWidget(card)

    assert isinstance(card, Card)
    assert card.title == "Net Profit"


def test_optional_slots_are_hidden_when_not_given(qtbot):
    card = StatCard("Total")
    qtbot.addWidget(card)

    assert card._suffix_label.isVisibleTo(card) is False
    assert card._caption_label.isVisibleTo(card) is False
    assert card._badge_label.isVisibleTo(card) is False


def test_suffix_and_caption_appear_when_given(qtbot):
    card = StatCard(
        "Est. Database Size", value="1.4", suffix="GB", caption="on-disk SQLite"
    )
    qtbot.addWidget(card)

    assert card.value == "1.4"
    assert card._suffix_label.isVisibleTo(card) is True
    assert card.caption == "on-disk SQLite"
    assert card._caption_label.isVisibleTo(card) is True


def test_badge_hides_itself_again_when_cleared(qtbot):
    card = StatCard("Win rate")
    qtbot.addWidget(card)

    card.set_badge("+12.34%", tone=Tone.POSITIVE)
    assert card.badge_text == "+12.34%"
    assert card._badge_label.isVisibleTo(card) is True

    card.set_badge("")
    assert card._badge_label.isVisibleTo(card) is False


def test_tone_reaches_the_rendered_value_qss(qtbot, fake_theme_bridge):
    card = StatCard("Net Profit")
    qtbot.addWidget(card)

    card.set_value("-812.40", tone=Tone.NEGATIVE)
    assert "<danger>" in card._value_label.styleSheet()

    card.set_value("812.40", tone=Tone.POSITIVE)
    assert "<success>" in card._value_label.styleSheet()

    card.set_value("0.00")
    assert "<textPrimary>" in card._value_label.styleSheet()


def test_badge_tone_survives_the_role_being_reapplied(qtbot, fake_theme_bridge):
    """The tone override must land in a block Qt will actually apply.

    This test used to assert the stylesheet *string* ended in the tone
    token, and that is exactly how it missed a real break: once `BUG-008`
    gave `BADGE` a selector block, `set_badge` was appending a bare
    `color:` after a closing brace. Qt discards such a property, so the
    tone stopped rendering — while the string still ended in the right
    token and the assertion still passed.

    So assert on structure, not on the tail: the token must sit inside a
    braced rule, and nothing may dangle after the last `}`.
    """
    card = StatCard("Drawdown")
    qtbot.addWidget(card)

    card.set_badge("Rủi ro", tone=Tone.NEGATIVE)

    qss = card._badge_label.styleSheet()
    assert "<danger>" in qss
    assert qss.rstrip().endswith("}"), (
        f"tone override is dangling outside a rule block, Qt will ignore it: {qss!r}"
    )
    _, _, after_last_block = qss.rpartition("}")
    assert after_last_block.strip() == ""


def test_tone_resolves_through_the_palette_not_a_baked_colour(qtbot):
    """The whole reason `Tone` exists rather than a colour parameter: the
    consumer passes `BULL_COLOR`/`BEAR_COLOR` hex strings today.

    The rendered QSS does of course contain a hex — that is what a token
    resolves *to*. What matters is that it came from the live palette, so
    a palette change reaches this widget. `guards.find_inline_stylesheets`
    covers the other half (no literal in the source); see
    `test_no_literal_colours_in_the_surfaces_package`.
    """
    from sagittarius_engine.extensions.pyside_mvc.tokens import get_theme_bridge

    card = StatCard("Profit factor")
    qtbot.addWidget(card)

    card.set_value("1.8", tone=Tone.POSITIVE)

    live_success = str(get_theme_bridge().value("success"))
    assert live_success in card._value_label.styleSheet()


def test_the_headline_figure_is_actually_headline_sized(qtbot, fake_theme_bridge):
    """The defect that motivated `STAT_VALUE`: this card calls its value a
    headline figure and shipped with no font rule on it at all, so it
    rendered at the widget default while the caption beside it was
    explicitly sized. Size and weight must come from the role."""
    card = StatCard("Net profit")
    qtbot.addWidget(card)

    card.set_value("1,284.50", tone=Tone.POSITIVE)

    qss = card._value_label.styleSheet()
    assert "<fontSizeXl>" in qss
    assert "font-weight: bold" in qss


def test_the_value_tone_lands_in_a_rule_qt_will_apply(qtbot, fake_theme_bridge):
    """Same structural trap as `BUG-009`: the per-instance colour is
    appended after the role's block, so it must carry its own selector
    rather than dangle as a bare property."""
    card = StatCard("Net profit")
    qtbot.addWidget(card)

    card.set_value("-42.10", tone=Tone.NEGATIVE)

    qss = card._value_label.styleSheet()
    assert "<danger>" in qss
    assert qss.rstrip().endswith("}"), f"tone override dangles, Qt drops it: {qss!r}"


def test_the_card_lifts_under_the_pointer(qtbot, fake_theme_bridge):
    """`STAT_CARD` exists to carry this. Expressed as QSS `:hover`, not an
    enterEvent/leaveEvent pair, so it cannot get stuck in the hovered look
    when a leave event is missed."""
    card = StatCard("Net profit")
    qtbot.addWidget(card)

    assert ".StatCard:hover" in card.styleSheet()
    assert "<stateHoverBg>" in card.styleSheet()


def test_the_title_text_survives_round_trip(qtbot, fake_theme_bridge):
    """The title is styled, never rewritten. Uppercasing it here would make
    the inherited `Card.title` lossy — a caller could not read back what it
    set."""
    card = StatCard("Net Profit")
    qtbot.addWidget(card)

    assert card.title == "Net Profit"
    assert "<muted>" in card._title_label.styleSheet()
