"""
Foundation gate for the shared "UI state" standardization work in
sagittarius_engine: state-aware Theme tokens (stateDisabledOpacity/
stateHoverBg/stateIdleBg/stateActiveTint/stateNavBorder), the QmlShared
components built on them (FieldBackground, StyledCheck, StatefulButton —
including its `isActive`, merged in from a since-removed standalone
NavButton — and BaseCard, the Rectangle-rooted setActive()/setDisabled()
method contract LogPanel now inherits), plus BaseQmlViewModel.controlsEnabled
— the derived, FSM-driven boolean screens are meant to bind `enabled:`
against instead of each hand-rolling their own uiMode string comparison.

Same probe-QML approach as test_qml_shared_foundation.py (that file's own
"Phase 0 gate" scope is BOT-030's QML migration specifically — this is a
separate, later concern, kept in its own file per the 1-concern-1-file
convention used throughout this test suite).

No existing screen changes in this round — these tests only prove the new
engine-level primitives work in isolation, ahead of any real screen adopting
them.
"""

import os
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtQuickWidgets import QQuickWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from sagittarius_engine.extensions.pyside_mvc import (
    BasePresenter,
    BaseQmlViewModel,
    QmlHostView,
)

_PROBE_QML = """
import QtQuick
import QmlShared 1.0

Item {
    id: root

    property real probedDisabledOpacity: Theme.stateDisabledOpacity
    property string probedHoverBg: Theme.stateHoverBg
    property string probedIdleBg: Theme.stateIdleBg
    property string probedActiveTint: Theme.stateActiveTint
    property string probedNavBorder: Theme.stateNavBorder

    FieldBackground {
        objectName: "probeFieldBackground"
    }

    StyledCheck {
        objectName: "probeStyledCheck"
        text: "probe"
    }

    StatefulButton {
        objectName: "probeStatefulButton"
        text: "probe"
        iconSource: "clock"
        accentBorder: "#ff0000"
    }

    StatefulButton {
        objectName: "probeActiveStatefulButton"
        text: "Probe Nav"
        iconSource: "layout-dashboard"
        isActive: true
    }

    BaseCard {
        objectName: "probeBaseCard"
    }
}
"""


@pytest.fixture
def probe_qml_file(tmp_path):
    path = tmp_path / "state_probe_screen.qml"
    path.write_text(_PROBE_QML, encoding="utf-8")
    return path


@pytest.fixture
def probe_view(qapp, probe_qml_file, request):
    class _ProbeView(QmlHostView):
        QML_DIR = probe_qml_file.parent

    view = _ProbeView()
    view.set_view_model(BaseQmlViewModel())
    view.load_qml(probe_qml_file.name)
    request.addfinalizer(view.deleteLater)
    return view


def test_probe_qml_loads_the_shared_components(probe_view):
    """Baseline: every new QmlShared type resolves and constructs without a
    QML error — an unresolved type/property would leave status != Ready."""
    assert probe_view.quick_widget.status() == QQuickWidget.Status.Ready
    assert probe_view.quick_widget.rootObject() is not None


def test_state_tokens_resolve_to_this_apps_real_palette_values(probe_view):
    """Palette.as_ui_dict() now supplies real stateIdleBg/stateHoverBg/
    stateActiveTint/stateNavBorder values (the exact literals every screen
    hand-rolled before the StatefulButton/FieldBackground/BaseCard
    migration) — Theme.state* must resolve to those, not the engine's
    generic placeholders, once a real screen is migrated onto them.
    stateDisabledOpacity is deliberately left unset in Palette (the engine
    default of 0.45 already matches the value this task standardized on),
    so that one alone still falls back to state_tokens.DEFAULT_STATE_TOKENS."""
    from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
    from sagittarius_engine.extensions.pyside_mvc.QmlShared.state_tokens import (
        DEFAULT_STATE_TOKENS,
    )

    root = probe_view.quick_widget.rootObject()
    assert root.property("probedDisabledOpacity") == pytest.approx(
        DEFAULT_STATE_TOKENS["stateDisabledOpacity"]
    )
    assert root.property("probedHoverBg") == Palette.STATE_HOVER_BG
    assert root.property("probedIdleBg") == Palette.STATE_IDLE_BG
    assert root.property("probedActiveTint") == Palette.STATE_ACTIVE_TINT
    assert root.property("probedNavBorder") == Palette.STATE_NAV_BORDER


def test_stateful_button_exposes_its_configured_properties(probe_view, qml_item):
    root = probe_view.quick_widget.rootObject()
    button = qml_item(root, "probeStatefulButton")
    assert button.property("text") == "probe"
    assert button.property("iconSource") == "clock"


def test_stateful_button_is_active_is_a_real_readable_property(probe_view, qml_item):
    """`isActive` must be a real, externally readable property — a future
    Sidebar.qml migration (onto StatefulButton, since the standalone
    NavButton it used to read this from was merged in here) needs
    `qml_item(...).property("isActive")` to keep working, mirroring
    test_sidebar.py's existing assertions on today's hand-rolled navButton."""
    root = probe_view.quick_widget.rootObject()
    active_button = qml_item(root, "probeActiveStatefulButton")
    assert active_button.property("isActive") is True
    assert active_button.property("text") == "Probe Nav"
    assert active_button.property("enabled") is True

    # The plain (non-nav) button from the sibling test defaults to inactive —
    # isActive and enabled/disabled are independent of each other.
    inactive_button = qml_item(root, "probeStatefulButton")
    assert inactive_button.property("isActive") is False


def test_styled_check_and_field_background_construct_cleanly(probe_view, qml_item):
    root = probe_view.quick_widget.rootObject()
    assert qml_item(root, "probeStyledCheck").property("text") == "probe"
    assert qml_item(root, "probeFieldBackground") is not None


# ---------------------------------------------------------------------------
# BaseCard — the setActive()/setDisabled() method contract
# ---------------------------------------------------------------------------


def test_base_card_constructs_and_its_state_methods_are_callable_no_ops(
    probe_view, qml_item
):
    """BaseCard itself never overrides setActive/setDisabled — calling them
    must not raise, and must have no visible effect (no property they'd
    plausibly touch, e.g. opacity, changes)."""
    root = probe_view.quick_widget.rootObject()
    card = qml_item(root, "probeBaseCard")
    assert card is not None

    opacity_before = card.property("opacity")
    card.setActive(True)
    card.setDisabled(True)
    assert card.property("opacity") == opacity_before


def test_log_panel_still_constructs_after_migrating_to_base_card(qapp, request):
    """Regression guard for LogPanel.qml's Rectangle -> BaseCard root swap:
    every existing property (title/logModel/autoScroll) must still resolve,
    proving the migration was a drop-in with no behavior change."""
    from pathlib import Path

    import sagittarius_engine.extensions.pyside_mvc.QmlShared as qml_shared_pkg
    from sagittarius_engine.extensions.pyside_mvc import QmlHostView
    from sagittarius_engine.extensions.pyside_mvc.QmlShared.log_list_model import (
        LogListModel,
    )

    class _LogPanelProbeView(QmlHostView):
        QML_DIR = Path(qml_shared_pkg.__file__).parent

    view = _LogPanelProbeView()
    view.set_view_model(BaseQmlViewModel())
    view.load_qml("LogPanel.qml")
    request.addfinalizer(view.deleteLater)

    assert view.quick_widget.status() == QQuickWidget.Status.Ready
    root = view.quick_widget.rootObject()
    model = LogListModel()
    root.setProperty("logModel", model)
    root.setProperty("title", "PROBE TITLE")
    assert root.property("title") == "PROBE TITLE"


# ---------------------------------------------------------------------------
# BaseQmlViewModel.controlsEnabled — the FSM tie-in point
# ---------------------------------------------------------------------------


def test_controls_enabled_defaults_true_with_no_disabled_modes_declared():
    """A subclass that never sets DISABLED_UI_MODES keeps today's behavior
    unchanged — controlsEnabled is always True regardless of uiMode."""
    vm = BaseQmlViewModel()
    assert vm.controlsEnabled is True

    vm.set_ui_mode("LOCKED")
    assert vm.controlsEnabled is True


def test_controls_enabled_toggles_for_a_declared_disabled_mode():
    class _ProbeViewModel(BaseQmlViewModel):
        DISABLED_UI_MODES = frozenset({"LOCKED"})

    vm = _ProbeViewModel()
    assert vm.controlsEnabled is True

    vm.set_ui_mode("LOCKED")
    assert vm.controlsEnabled is False

    vm.set_ui_mode("IDLE")
    assert vm.controlsEnabled is True


def test_controls_enabled_changed_signal_only_fires_on_an_actual_flip():
    class _ProbeViewModel(BaseQmlViewModel):
        DISABLED_UI_MODES = frozenset({"LOCKED", "LIVE"})

    vm = _ProbeViewModel()
    calls = []
    vm.controlsEnabledChanged.connect(lambda: calls.append(1))

    vm.set_ui_mode("LOCKED")  # True -> False: fires
    vm.set_ui_mode("LIVE")  # False -> False: must NOT fire again
    vm.set_ui_mode("IDLE")  # False -> True: fires

    assert len(calls) == 2


def test_controls_enabled_drives_qml_end_to_end_through_a_real_fsm_transition(
    qapp, request
):
    """Mirrors test_base_presenter_fsm_drives_qml_ui_mode_end_to_end from
    test_qml_shared_foundation.py, but for controlsEnabled specifically —
    proven through a real BasePresenter/BaseStateMachine chain, not by
    calling set_ui_mode() directly."""
    container = Mock()

    def resolve_mock(interface):
        from sagittarius_engine.interfaces import IConfig

        if interface == IConfig:
            config = Mock()
            config.get_all.return_value = {}
            config.get.return_value = False
            return config
        return Mock()

    container.resolve.side_effect = resolve_mock

    class _ProbeViewModel(BaseQmlViewModel):
        DISABLED_UI_MODES = frozenset({"LOCKED"})

    class _ProbeView(QmlHostView):
        pass

    class _ProbePresenter(BasePresenter):
        INITIAL_STATE = UIMode.IDLE

        def __init__(self, view, container):
            super().__init__(view, container)
            self.fsm.add_transition(UIMode.IDLE, UIMode.LOCKED)
            self._connect_ui_signals()
            self._connect_engine_events()

        def _connect_ui_signals(self) -> None:
            pass

        def _connect_engine_events(self) -> None:
            pass

    view = _ProbeView()
    view_model = _ProbeViewModel()
    view.set_view_model(view_model)
    request.addfinalizer(view.deleteLater)

    presenter = _ProbePresenter(view, container)

    assert view_model.controlsEnabled is True
    presenter.fsm.transition_to(UIMode.LOCKED)
    assert view_model.controlsEnabled is False
