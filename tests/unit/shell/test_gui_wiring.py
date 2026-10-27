"""`EPIC-038A` — the GUI composition keeps everything the split moved to it.

`create_app` no longer names a UI package, so three things the GUI relied on
left it: the UI-failure subscriber, the icon-asset validator and the Qt package
check (and a fourth the DESIGN missed, the Engine-build check, whose lookups
import the Engine's Qt package). `add_gui_wiring` puts them back for the GUI
entry point only. These tests build the graph the way `app_bootstrapper.build()`
does — `create_gui_app`, then `boot()` — and ask the graph,
not the wiring function (`CS-002`: a test that constructs the subscriber itself
proves nothing about whether production does).
"""

from __future__ import annotations

import os

import pytest
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.engine_capability_validator_extension import (
    EngineCapabilityValidatorExtension,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.vps_feed_settings import (
    VpsFeedSettings,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.shell.gui_wiring import create_gui_app
from Sagittarius_Elite_Warrior.src.shell.qt_package_check import (
    QtPackageCheckExtension,
)
from Sagittarius_Elite_Warrior.src.shell.ui_action_failure import (
    UiActionFailureSubscriber,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import AssetValidatorExtension
from sagittarius_engine import App
from sagittarius_engine.extensions.dependency_validator import (
    DependencyValidatorExtension,
)
from sagittarius_engine.extensions.pyside_mvc.safety.ui_action_events import (
    UiActionFailedEvent,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.runtime.tasks.events import TaskFailed

_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "src",
    "config",
)

_GUI_ADDITIONS = (
    QtPackageCheckExtension,
    EngineCapabilityValidatorExtension,
    AssetValidatorExtension,
)


def _config() -> ConfigManager:
    config_manager = ConfigManager()
    config_manager.load_json(os.path.join(_CONFIG_DIR, "app_config.json"))
    config_manager.load_json(os.path.join(_CONFIG_DIR, "user_config.json"))
    return config_manager


@pytest.fixture
def gui_app():
    app = create_gui_app(_config())
    yield app
    app.stop()


@pytest.fixture
def shared_app():
    app = create_app(_config())
    yield app
    app.stop()


def _registered(app: App, kind: type) -> list[object]:
    return [e for e in app.context.modules if isinstance(e, kind)]


def test_the_gui_graph_subscribes_somebody_to_every_failure_event(gui_app):
    """`BUG-126` for the graph the GUI entry point builds: all three sources."""
    bus = gui_app.event_bus
    assert isinstance(bus, MemoryEventBus)

    unheard = [
        event_type.__name__
        for event_type in (BulkSyncProgressEvent, UiActionFailedEvent, TaskFailed)
        if not bus.get_handlers(event_type)
    ]

    assert unheard == [], f"{unheard} reach nobody in the GUI composition"


def test_the_gui_graph_owns_the_ui_failure_subscriber(gui_app):
    assert isinstance(
        gui_app.context.container.resolve(UiActionFailureSubscriber),
        UiActionFailureSubscriber,
    )


def test_the_gui_graph_registers_the_asset_validator_and_the_qt_check(gui_app):
    assert len(_registered(gui_app, AssetValidatorExtension)) == 1
    qt_checks = _registered(gui_app, QtPackageCheckExtension)
    assert len(qt_checks) == 1
    assert isinstance(qt_checks[0], QtPackageCheckExtension)
    assert {"PySide6", "pyqtgraph"} <= set(qt_checks[0].required_packages)


def test_the_gui_graph_registers_the_engine_build_check_after_the_presence_check(
    gui_app,
):
    """The check the DESIGN's three blockers missed: its lookups import the
    Engine's Qt package, so it belongs to the GUI, and it still depends on the
    shared presence check by name (`BOT-119`)."""
    builds = _registered(gui_app, EngineCapabilityValidatorExtension)
    presence = _registered(gui_app, DependencyValidatorExtension)

    assert len(builds) == 1
    assert isinstance(builds[0], EngineCapabilityValidatorExtension)
    assert isinstance(presence[0], DependencyValidatorExtension)
    assert presence[0].descriptor.name in builds[0].dependencies


def test_the_gui_graph_keeps_exactly_one_presence_check_and_it_names_no_qt(gui_app):
    """The shared check stays the only `DependencyValidatorExtension`, and
    `EngineCapabilityValidatorExtension.dependencies` still resolves to it."""
    presence = _registered(gui_app, DependencyValidatorExtension)
    assert len(presence) == 1
    assert isinstance(presence[0], DependencyValidatorExtension)
    assert presence[0].required_packages == ["sqlalchemy"]


def test_the_shared_graph_registers_none_of_the_gui_additions(shared_app):
    """The other direction: what the headless entry point builds must not have
    them, or it needs Qt. (The import-level proof is the architecture guard; the
    boot-level proof is the sanity test with PySide6 blocked.)"""
    present = [
        kind.__name__ for kind in _GUI_ADDITIONS if _registered(shared_app, kind)
    ]
    assert present == []
    bus = shared_app.event_bus
    assert isinstance(bus, MemoryEventBus)
    assert not bus.get_handlers(UiActionFailedEvent)


def test_the_gui_checks_boot_before_any_module(gui_app):
    """They fail the boot fast; one that ran after the bots module had restored
    bots and started watches would exit with the work half done. The Engine
    boots a higher `priority` first, and the GUI wiring registers them last."""
    gui_app.boot()

    order = [
        e.descriptor.name for e in gui_app.context.extension_manager.sorted_extensions
    ]
    first_work = order.index("ThreadManagerExtension")
    for kind in _GUI_ADDITIONS:
        assert order.index(kind.__name__) < first_work, order
    assert order.index("DependencyValidatorExtension") < order.index(
        "EngineCapabilityValidatorExtension"
    ), order


def test_the_gui_graph_runs_no_vps_feed_and_the_shared_graph_does(gui_app, shared_app):
    """`EPIC-047H`: a desktop never reads the exchange for the host's files; the headless graph does."""
    gui = gui_app.context.container.resolve(VpsFeedSettings)
    shared = shared_app.context.container.resolve(VpsFeedSettings)

    assert (gui.feed_enabled, shared.feed_enabled) == (False, True)
