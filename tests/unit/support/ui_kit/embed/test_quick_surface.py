"""`QuickSurface` contract — `BUG-115`'s regression tests, at the tier that
can see them.

The on-screen symptom (a black or see-through QML body) lives on the
texture rendering path of a real desktop session, which `offscreen` cannot
reach — `BUG-115` §2.4 measured that every `grab()` looks correct while the
screen is wrong. So the headless tier pins the *mechanism* whose violation
produces the symptom: the scene clears to an opaque colour equal to the
token its declared surface role paints. The screen-level proof is
`scripts/quick_surface_desktop_probe.py` (real display or `xvfb-run`).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
from PySide6.QtCore import Property, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QSizePolicy
from Sagittarius_Elite_Warrior.src.support.ui_kit.embed import (
    QuickSizePolicy,
    QuickSurface,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    StyleRole,
    background_token,
)
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

_OPAQUE_ALPHA = 255
_PROBE_WIDTH = 120
_PROBE_HEIGHT = 40


class _Vm(QObject):
    def __init__(self) -> None:
        super().__init__()
        self._label = "hello"

    @Property(str, constant=True)
    def label(self) -> str:
        return self._label


@pytest.fixture
def probe_qml(tmp_path: Path) -> Path:
    path = tmp_path / "Probe.qml"
    path.write_text(
        "import QtQuick\n"
        "Item {\n"
        f"    implicitWidth: {_PROBE_WIDTH}; implicitHeight: {_PROBE_HEIGHT}\n"
        '    Text { objectName: "probeText"; text: vm.label; color: Theme.textPrimary }\n'
        "}\n",
        encoding="utf-8",
    )
    return path


def _live_colour(token: str) -> QColor:
    return QColor(str(get_theme_bridge().value(token)))


def test_clears_to_the_opaque_token_of_its_surface_role(qapp, probe_qml):
    surface = QuickSurface(probe_qml, surface=StyleRole.SURFACE, context={"vm": _Vm()})
    colour = surface.quick_widget.quickWindow().color()
    assert colour.alpha() == _OPAQUE_ALPHA
    assert colour.rgb() == _live_colour(background_token(StyleRole.SURFACE)).rgb()
    assert surface.surface_role is StyleRole.SURFACE


def test_a_header_surface_clears_to_the_header_token(qapp, probe_qml):
    surface = QuickSurface(
        probe_qml, surface=StyleRole.TABLE_HEADER, context={"vm": _Vm()}
    )
    colour = surface.quick_widget.quickWindow().color()
    assert colour.rgb() == _live_colour("bgCardHeader").rgb()


def test_a_role_without_a_static_background_is_refused_at_construction(qapp, probe_qml):
    with pytest.raises(ValueError, match="no static opaque background"):
        QuickSurface(
            probe_qml, surface=StyleRole.SELECTABLE_CARD, context={"vm": _Vm()}
        )


def test_context_objects_reach_the_scene_and_are_kept_alive(qapp, probe_qml, qml_item):
    surface = QuickSurface(probe_qml, context={"vm": _Vm()})
    # The only reference to the `_Vm` is the one `QuickSurface` holds — a
    # borrowed context property would already be dead here.
    assert qml_item(surface.root_object, "probeText").property("text") == "hello"


def test_a_broken_qml_file_raises_instead_of_rendering_a_blank_box(qapp, tmp_path):
    broken = tmp_path / "Broken.qml"
    broken.write_text("import QtQuick\nItem { this is not qml }\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="QML failed to load"):
        QuickSurface(broken, context={"vm": _Vm()})


def test_object_name_lands_on_the_inner_widget(qapp, probe_qml):
    surface = QuickSurface(probe_qml, context={"vm": _Vm()}, object_name="qmlBody")
    assert surface.quick_widget.objectName() == "qmlBody"


def test_fill_lets_the_layout_size_the_scene(qapp, probe_qml):
    surface = QuickSurface(probe_qml, context={"vm": _Vm()})
    surface.resize(400, 300)
    surface.show()
    qapp.processEvents()
    root = surface.root_object
    assert (root.property("width"), root.property("height")) == (400, 300)
    surface.close()


def test_hug_sizes_the_widget_to_the_scene(qapp, probe_qml):
    surface = QuickSurface(
        probe_qml, context={"vm": _Vm()}, size_policy=QuickSizePolicy.HUG
    )
    surface.show()
    qapp.processEvents()
    assert surface.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed
    assert (surface.sizeHint().width(), surface.sizeHint().height()) == (
        _PROBE_WIDTH,
        _PROBE_HEIGHT,
    )
    surface.close()
