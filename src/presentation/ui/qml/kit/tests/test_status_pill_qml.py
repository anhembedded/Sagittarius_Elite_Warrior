"""Render tests for `StatusPill.qml`."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101, PLR2004

from __future__ import annotations


def test_the_four_tones_get_distinct_colours(load_qml, qml_item):
    quick, root = load_qml("StatusPill.qml")
    dot = qml_item(root, "statusPillDot")
    label = qml_item(root, "statusPillLabel")

    dot_colours = {}
    label_colours = {}
    for tone in ("idle", "active", "success", "danger"):
        root.setProperty("tone", tone)
        dot_colours[tone] = str(dot.property("color"))
        label_colours[tone] = str(label.property("color"))
    quick.close()
    quick.deleteLater()

    assert len(set(dot_colours.values())) == 4
    assert dot_colours == label_colours


def test_text_is_shown_as_given(load_qml, qml_item):
    quick, root = load_qml("StatusPill.qml")
    root.setProperty("text", "WS: LIVE")
    label = qml_item(root, "statusPillLabel")

    assert label.property("text") == "WS: LIVE"
    quick.close()
    quick.deleteLater()


def test_the_dot_can_be_hidden(load_qml, qml_item):
    quick, root = load_qml("StatusPill.qml")
    root.setProperty("showDot", False)
    dot = qml_item(root, "statusPillDot")

    assert dot.property("visible") is False
    quick.close()
    quick.deleteLater()
