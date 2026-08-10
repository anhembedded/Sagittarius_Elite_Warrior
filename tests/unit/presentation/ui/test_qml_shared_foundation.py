"""
Phase 0 gate for BOT-030 (full QML migration).

Proves the two load-bearing claims the whole migration plan rests on,
before any real screen is built on top of them:

1. `BasePresenter._bind_fsm_to_ui` duck-types `view.apply_ui_mode(...)`,
   so a QML-hosting view can route FSM state into a QML-bindable property
   with ZERO changes to the shared `sagittarius_engine` package.
2. The value actually lands in QML — asserted by reading it back off the
   loaded QML root object, not just off the Python ViewModel (which would
   only prove Python talked to itself).
"""

import os
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtQuickWidgets import QQuickWidget  # noqa: E402

from sagittarius_engine.extensions.pyside_mvc import BasePresenter  # noqa: E402

from sagittarius_engine.extensions.pyside_mvc import (  # noqa: E402
    BaseQmlViewModel,
    QmlHostView,
    get_theme_bridge,
)

from Binace_Bot.src.presentation.ui.assets import IconTheme, Palette  # noqa: E402
from Binace_Bot.src.presentation.ui.constants import UIMode  # noqa: E402

_PROBE_QML = """
import QtQuick

Rectangle {
    color: Theme.bg
    // Bound to both bridges under test: the FSM-driven uiMode (via
    // viewModel) and the shared Theme singleton.
    property string probedMode: viewModel.uiMode
    property string probedAccent: Theme.accent
}
"""


@pytest.fixture
def probe_qml_file(tmp_path):
    path = tmp_path / "probe_screen.qml"
    path.write_text(_PROBE_QML, encoding="utf-8")
    return path


@pytest.fixture
def probe_view(qapp, probe_qml_file, request):
    """A minimal QmlHostView loading the probe QML, with a ViewModel attached."""

    class _ProbeView(QmlHostView):
        QML_DIR = probe_qml_file.parent

    view = _ProbeView()
    view.set_view_model(BaseQmlViewModel())
    view.load_qml(probe_qml_file.name)
    request.addfinalizer(view.deleteLater)
    return view


def test_probe_qml_loads_with_theme_and_view_model(probe_view):
    """Baseline: the QML document resolves both context properties (`Theme`
    and `viewModel`) at parse time — an unresolved name would leave status
    != Ready with an error."""
    assert probe_view.quick_widget.status() == QQuickWidget.Status.Ready
    assert probe_view.quick_widget.rootObject() is not None


def test_apply_ui_mode_reaches_qml_property(probe_view):
    """
    The core Phase 0 claim: QmlHostView.apply_ui_mode() — the method
    BasePresenter calls on FSM transitions — propagates into QML.
    Asserted by reading the value back off the QML root object.
    """
    root = probe_view.quick_widget.rootObject()
    assert root.property("probedMode") == "IDLE"  # BaseQmlViewModel default

    probe_view.apply_ui_mode(UIMode.LOCKED)
    assert root.property("probedMode") == "LOCKED"

    # Plain strings work too — apply_ui_mode normalizes enum-or-string.
    probe_view.apply_ui_mode("LIVE")
    assert root.property("probedMode") == "LIVE"


def test_theme_singleton_value_reaches_qml(probe_view):
    """The shared Theme bridge resolves in QML to the real palette value,
    so screens can drop per-file hardcoded hex."""
    root = probe_view.quick_widget.rootObject()
    assert root.property("probedAccent") == Palette.ACCENT


def test_base_presenter_fsm_drives_qml_ui_mode_end_to_end(probe_view):
    """
    THE Phase 0 claim, proven end-to-end through the REAL BasePresenter (not
    by calling apply_ui_mode directly): a presenter's FSM transition must
    reach the QML property with zero changes to the shared
    `sagittarius_engine.extensions.pyside_mvc` package.

    BasePresenter._bind_fsm_to_ui looks for `view.control_card.apply_ui_mode`
    first and falls back to `view.apply_ui_mode` — QmlHostView provides the
    latter, so this works purely by duck typing.
    """
    container = Mock()

    def resolve_mock(interface):
        from sagittarius_engine.interfaces import IConfig

        if interface == IConfig:
            config = Mock()
            config.get_all.return_value = {}
            config.get.return_value = False  # dev.mode off
            return config
        return Mock()

    container.resolve.side_effect = resolve_mock

    class _ProbePresenter(BasePresenter):
        INITIAL_STATE = UIMode.IDLE

        def __init__(self, view, container):
            super().__init__(view, container)
            self.fsm.add_transition(UIMode.IDLE, UIMode.LOCKED)
            self.fsm.add_transition(UIMode.LOCKED, UIMode.LIVE)
            self._connect_ui_signals()
            self._connect_engine_events()

        def _connect_ui_signals(self) -> None:
            """No UI signals on this probe screen."""

        def _connect_engine_events(self) -> None:
            """No engine events on this probe screen."""

    presenter = _ProbePresenter(probe_view, container)
    root = probe_view.quick_widget.rootObject()

    presenter.fsm.transition_to(UIMode.LOCKED)
    assert root.property("probedMode") == "LOCKED"

    presenter.fsm.transition_to(UIMode.LIVE)
    assert root.property("probedMode") == "LIVE"


def test_theme_bridge_is_a_shared_singleton():
    assert get_theme_bridge() is get_theme_bridge()


def test_icon_theme_stays_in_sync_with_palette():
    """IconTheme now sources from Palette — guards against the two drifting
    apart again if someone edits one and not the other."""
    assert IconTheme.ACCENT == Palette.ACCENT
    assert IconTheme.SUCCESS == Palette.SUCCESS
    assert IconTheme.DANGER == Palette.DANGER
    assert IconTheme.MUTED == Palette.MUTED
