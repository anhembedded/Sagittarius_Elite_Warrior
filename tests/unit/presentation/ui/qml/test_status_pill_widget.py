"""Render/interaction tests for `StatusPillWidget` — the inline (non-modal)
`QQuickWidget` host for `StatusPill.qml`.

Thin on purpose (`qml-rule.md` §7): `StatusPill.qml` itself already has its
own render tests (`qml/kit/tests/test_status_pill_qml.py`, including the
four-tones-get-distinct-colours assertion). This file only proves the
*host* wires plain setters to the right QML properties — the render-time
class of error `mypy`/`ruff` cannot see for a bare `.py` file that
references property names by string.

`EPIC-015` Phase 4 — this is the first `kit/` widget embedded beside the
live pyqtgraph chart (`DevBoardPanel`'s header). This test suite runs
headless (`QT_QPA_PLATFORM=offscreen`) and can only confirm the QML scene
constructs and its bindings are correct; it cannot observe real chart
rendering quality (flicker/FPS) — see the task's own report for what a
human must still verify in the running app.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtQuickWidgets import QQuickWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.kit.status_pill_widget import (
    StatusPillWidget,
)
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.qml._qml_test_support import (
    find_named,
)


def _widget(qapp) -> StatusPillWidget:
    widget = StatusPillWidget()
    widget.resize(120, 22)
    widget.show()
    qapp.processEvents()
    return widget


def test_loads_ready_with_a_real_root_object(qapp):
    widget = _widget(qapp)

    assert widget.status() is QQuickWidget.Status.Ready
    assert widget.root_object is not None
    widget.close()


def test_set_text_reaches_the_qml_root_and_label(qapp):
    widget = _widget(qapp)

    widget.set_text("WS: LIVE")
    qapp.processEvents()

    root = widget.root_object
    assert root.property("text") == "WS: LIVE"
    label = find_named(root, "statusPillLabel")
    assert label.property("text") == "WS: LIVE"
    widget.close()


@pytest.mark.parametrize("tone", ["idle", "active", "success", "danger"])
def test_set_tone_reaches_the_qml_root_for_all_four_states(qapp, tone):
    widget = _widget(qapp)

    widget.set_tone(tone)
    qapp.processEvents()

    assert widget.root_object.property("tone") == tone
    widget.close()


def test_set_show_dot_reaches_the_dot_visibility(qapp):
    widget = _widget(qapp)

    widget.set_show_dot(False)
    qapp.processEvents()

    dot = find_named(widget.root_object, "statusPillDot")
    assert dot.property("visible") is False
    widget.close()
