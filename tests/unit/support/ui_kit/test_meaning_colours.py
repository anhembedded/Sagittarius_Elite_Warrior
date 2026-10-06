from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    LOSS_COLOUR,
    PROFIT_COLOUR,
    Tone,
    tone_colour,
)


def test_a_verdict_has_a_colour_and_no_verdict_has_none():
    assert tone_colour(Tone.POSITIVE) == PROFIT_COLOUR
    assert tone_colour(Tone.NEGATIVE) == LOSS_COLOUR
    assert tone_colour(Tone.NEUTRAL) is None


def test_profit_and_loss_are_told_apart():
    assert PROFIT_COLOUR != LOSS_COLOUR


def test_the_colour_returned_is_a_copy():
    colour = tone_colour(Tone.POSITIVE)
    assert colour is not None
    colour.setRed(0)
    assert tone_colour(Tone.POSITIVE) == PROFIT_COLOUR
