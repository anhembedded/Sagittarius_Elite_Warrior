"""Render tests for `StatCard.qml`."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101, PLR2004

from __future__ import annotations


def test_a_neutral_card_shows_the_given_text(load_qml, qml_item):
    quick, root = load_qml("StatCard.qml")
    root.setProperty("title", "Tỷ lệ thắng")
    root.setProperty("value", "10.33%")
    root.setProperty("caption", "92/891 lệnh")

    value = qml_item(root, "statCardValue")
    caption = qml_item(root, "statCardCaption")
    title = qml_item(root, "statCardTitle")

    assert value.property("text") == "10.33%"
    assert caption.property("text") == "92/891 lệnh"
    assert title.property("text") == "TỶ LỆ THẮNG"
    quick.close()
    quick.deleteLater()


def test_the_three_tones_give_the_value_distinct_colours(load_qml, qml_item):
    quick, root = load_qml("StatCard.qml")
    value = qml_item(root, "statCardValue")

    colours = {}
    for tone in ("neutral", "positive", "negative"):
        root.setProperty("tone", tone)
        colours[tone] = str(value.property("color"))
    quick.close()
    quick.deleteLater()

    assert len(set(colours.values())) == 3


def test_a_negative_tone_colours_both_value_and_caption_the_same(load_qml, qml_item):
    quick, root = load_qml("StatCard.qml")
    root.setProperty("value", "-8,193.54 USD")
    root.setProperty("caption", "-81.94%")
    root.setProperty("tone", "negative")

    value = qml_item(root, "statCardValue")
    caption = qml_item(root, "statCardCaption")
    title = qml_item(root, "statCardTitle")

    assert str(value.property("color")) == str(caption.property("color"))
    assert str(value.property("color")) != str(title.property("color"))
    quick.close()
    quick.deleteLater()


def test_a_neutral_card_leaves_the_caption_at_the_default_muted_colour(
    load_qml, qml_item
):
    quick, root = load_qml("StatCard.qml")
    root.setProperty("caption", "92/891 lệnh")
    root.setProperty("tone", "neutral")
    caption = qml_item(root, "statCardCaption")
    neutral_colour = str(caption.property("color"))

    root.setProperty("tone", "negative")
    tinted_colour = str(caption.property("color"))
    quick.close()
    quick.deleteLater()

    assert neutral_colour != tinted_colour


def test_title_never_gets_tinted_by_tone(load_qml, qml_item):
    quick, root = load_qml("StatCard.qml")
    title = qml_item(root, "statCardTitle")
    neutral_title_colour = str(title.property("color"))

    for tone in ("positive", "negative"):
        root.setProperty("tone", tone)
        assert str(title.property("color")) == neutral_title_colour
    quick.close()
    quick.deleteLater()


def test_suffix_and_badge_are_hidden_when_empty(load_qml, qml_item):
    quick, root = load_qml("StatCard.qml")
    suffix = qml_item(root, "statCardSuffix")
    badge = qml_item(root, "statCardBadge")

    assert suffix.property("visible") is False
    assert badge.property("visible") is False

    root.setProperty("suffix", "USD")
    root.setProperty("badgeText", "3d 4h")
    assert suffix.property("visible") is True
    assert badge.property("visible") is True
    quick.close()
    quick.deleteLater()


def test_badge_tone_is_independent_of_value_tone(load_qml, qml_item):
    quick, root = load_qml("StatCard.qml")
    root.setProperty("badgeText", "3d 4h")
    root.setProperty("tone", "negative")
    root.setProperty("badgeTone", "positive")

    value = qml_item(root, "statCardValue")
    badge_text = qml_item(root, "statCardBadgeText")

    assert str(value.property("color")) != str(badge_text.property("color"))
    quick.close()
    quick.deleteLater()
