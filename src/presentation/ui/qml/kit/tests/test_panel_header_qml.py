"""Render tests for `PanelHeader.qml`.

The "actions" slot (children declared inside a `PanelHeader { ... }` usage
land in its internal `Row`) is exercised by `LogPanel`'s and
`DialogShell`'s own tests, which each place real buttons there — this file
only covers what `PanelHeader` renders on its own.
"""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101

from __future__ import annotations


def test_title_renders_uppercased(load_qml, qml_item):
    quick, root = load_qml("PanelHeader.qml")
    root.setProperty("title", "system controls")

    label = qml_item(root, "panelHeaderTitle")
    assert label.property("text") == "SYSTEM CONTROLS"
    quick.close()
    quick.deleteLater()


def test_badge_is_hidden_when_empty(load_qml, qml_item):
    quick, root = load_qml("PanelHeader.qml")

    badge = qml_item(root, "panelHeaderBadge")
    assert badge.property("visible") is False
    quick.close()
    quick.deleteLater()


def test_badge_shows_when_text_is_set(load_qml, qml_item):
    quick, root = load_qml("PanelHeader.qml")
    root.setProperty("badgeText", "21")

    badge = qml_item(root, "panelHeaderBadge")
    assert badge.property("visible") is True
    quick.close()
    quick.deleteLater()
