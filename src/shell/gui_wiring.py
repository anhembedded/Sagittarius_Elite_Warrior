"""What the GUI adds to the shared composition (`EPIC-038A`).

`create_app` (`shell/composition_root.py`) builds the object graph both entry
points need and names no UI package, so it boots where PySide6 is not
installed. The GUI entry point builds its graph with `create_gui_app`, which is
`create_app` plus `add_gui_wiring` — one call, so the additions cannot be
forgotten, and they are always on **before `boot()`**: an extension registered
afterwards would miss the boot it exists to guard, and a subscriber registered
afterwards would miss a failure during it (`BUG-126`). The same two-phase shape
`app_bootstrapper.py` uses for the toast channel, added once a window exists.

This file is a composition-root file (`tests/unit/architecture/boundaries/
scan.py::COMPOSITION_ROOT_FILES`), as `composition_root.py` is: it names an
infrastructure adapter and the UI support package so that nothing else has to.
The guard that keeps the *shared* path Qt-free reads `composition_root.py` and
`main.py` and never reaches this file.

Four additions, each of which names Qt or needs it to run:

1. `UiActionFailureSubscriber` — a UI slot raised (the event's type is the
   Engine's Qt package); only the GUI can publish it.
2. `AssetValidatorExtension` — the icon files the UI draws exist; it reaches the
   Qt image classes through `icon_loader`.
3. `QtPackageCheckExtension` — PySide6 and pyqtgraph are installed.
4. `EngineCapabilityValidatorExtension` — the installed Engine build has the
   Qt workbench classes the UI is built on. Looking them up imports the Engine's
   Qt package, which on a machine without PySide6 failed and was reported as a
   stale Engine; the DESIGN's three blockers missed it (it fires at `boot()`,
   after the import-time one it hid behind).

The three checks boot before the modules (`PREFLIGHT_BOOT_PRIORITY`), as they
did when `create_app` registered them first.

Seam for a variant later: another entry point that owns a UI adds its own
function beside this one; the shared composition does not change.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.engine_capability_validator_extension import (
    EngineCapabilityValidatorExtension,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.shell.qt_package_check import (
    QtPackageCheckExtension,
)
from Sagittarius_Elite_Warrior.src.shell.system_failure_log import SystemFailureLog
from Sagittarius_Elite_Warrior.src.shell.system_failure_relay import (
    SystemFailureRelay,
)
from Sagittarius_Elite_Warrior.src.shell.ui_action_failure import (
    UiActionFailureSubscriber,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import (
    AssetValidatorExtension,
)
from sagittarius_engine import App
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


def add_gui_wiring(app: App) -> None:
    """Register the GUI's additions on `app`, which `create_app` returned and
    nobody has booted yet."""
    container = app.context.container
    # Registered as a singleton so the graph owns it, as `SystemFailureLog` is:
    # `bus.on()` alone would keep it alive through the bound handler, a
    # lifetime nobody reading the composition could see.
    container.singleton(
        UiActionFailureSubscriber,
        UiActionFailureSubscriber(
            app.context.event_bus,
            container.resolve(SystemFailureLog),
            container.resolve(SystemFailureRelay),
        ),
    )
    app.use(QtPackageCheckExtension())
    app.use(EngineCapabilityValidatorExtension())
    app.use(AssetValidatorExtension())


def create_gui_app(
    config_manager: ConfigManager, instance: IInstanceAccess | None = None
) -> App:
    """The object graph the GUI entry point boots: the shared composition plus
    the GUI's additions. `instance` is `create_app`'s (`EPIC-035H`)."""
    app = create_app(config_manager, instance)
    add_gui_wiring(app)
    return app
