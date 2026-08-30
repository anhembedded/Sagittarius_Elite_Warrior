"""Render/interaction tests for `ProgressBannerWidget` — the inline
(non-modal) `QQuickWidget` host for `ProgressBanner.qml`.

Thin on purpose (`qml-rule.md` §7): `ProgressBanner.qml` itself already has
its own render tests (`qml/kit/tests/test_progress_banner_qml.py`). This
file only proves the *host* wires plain setters/signal to the right QML
properties/signal — the render-time class of error `mypy`/`ruff` cannot
see for a bare `.py` file that references property names by string.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.kit.progress_banner_widget import (
    ProgressBannerWidget,
)
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.qml._qml_test_support import (
    find_named,
)


def _widget(qapp) -> ProgressBannerWidget:
    widget = ProgressBannerWidget()
    widget.resize(320, 60)
    widget.show()
    qapp.processEvents()
    return widget


def test_setters_reach_the_qml_root_properties(qapp):
    widget = _widget(qapp)

    widget.set_status_text("Đang đồng bộ nến: 45/100 (45%)")
    widget.set_percent(45.0)
    widget.set_indeterminate(False)
    widget.set_cancelling(False)
    widget.set_cancel_label("Hủy Tiến Trình (Cancel)")
    qapp.processEvents()

    root = widget.root_object
    assert root.property("statusText") == "Đang đồng bộ nến: 45/100 (45%)"
    assert root.property("percent") == 45.0
    assert root.property("indeterminate") is False
    assert root.property("cancelling") is False
    assert root.property("cancelLabel") == "Hủy Tiến Trình (Cancel)"

    status = find_named(root, "progressBannerStatusText")
    percent = find_named(root, "progressBannerPercentText")
    assert status.property("text") == "Đang đồng bộ nến: 45/100 (45%)"
    assert percent.property("text") == "45%"
    widget.close()


def test_set_indeterminate_hides_percent_and_shows_the_sweep(qapp):
    widget = _widget(qapp)
    widget.set_indeterminate(True)
    qapp.processEvents()

    root = widget.root_object
    assert find_named(root, "progressBannerPercentText").property("visible") is False
    assert (
        find_named(root, "progressBannerIndeterminateSweep").property("visible") is True
    )
    widget.close()


def test_set_cancelling_disables_and_relabels_the_button(qapp):
    widget = _widget(qapp)
    widget.set_cancelling(True)
    qapp.processEvents()

    button = find_named(widget.root_object, "progressBannerCancelButton")
    label = find_named(button, "buttonLabel")
    assert button.property("enabled") is False
    assert label.property("text") == "Đang hủy..."
    widget.close()


def test_clicking_the_qml_cancel_button_emits_cancel_requested(qapp):
    """A real click, not a hand-invoked signal (`qml-rule.md` §4.4/§7) —
    `QTest.mouseClick` exercises the actual `MouseArea`/`Button` path."""
    widget = _widget(qapp)
    button = find_named(widget.root_object, "progressBannerCancelButton")

    fired: list[None] = []
    widget.cancelRequested.connect(lambda: fired.append(None))

    centre = button.mapToScene(button.boundingRect().center())
    QTest.mouseClick(
        widget,
        Qt.MouseButton.LeftButton,
        pos=QPoint(int(centre.x()), int(centre.y())),
    )
    qapp.processEvents()

    assert fired == [None]
    widget.close()
