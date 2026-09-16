"""`seed_app_theme()` — the two calls any process must make before it builds
a widget from this app.

@par Why this exists as one function
Every widget in `kit/` resolves its QSS through `get_theme_bridge()`, and
every embedded QML scene is built by the engine's `create_quick_widget()`,
which requires `configure_app_qml()`. `app_bootstrapper.build()` makes both
calls — but it is not the only entry point that constructs widgets: the
preview runner, the shutdown probes, the benchmarking probes and the desktop
E2E scripts all assemble real screens without it.

Each of those had grown its own partial copy of the wiring: two called only
`get_theme_bridge(...)`, three called only `configure_app_qml(...)`, and the
comments in the first pair still described `configure_app_qml()` as
something the app no longer needed (true only during `EPIC-006F`'s
QML-free window, and false again since `EPIC-015`). `BOT-132` turned the
half that was missing into a hard failure — `create_quick_widget()` raises
without `configure_app_qml()` — which is how the shutdown probes surfaced:
two integration tests that launch them as real subprocesses went red.

So this is the one place that knows what "the app's theme is ready" means.
A caller that builds widgets calls it; nobody spells out the pair again.

@par Order matters, and both calls are needed
`configure_app_qml()` registers the palette/icon wiring the engine's QML
factory reads. `get_theme_bridge()` is a separate first-caller-wins
singleton that `apply_role()` reads for QtWidgets QSS; seeding it here with
the same palette is what keeps a QtWidgets surface and the QML scene
embedded on it rendering from one source (`BUG-115`).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import Palette, get_icon_loader
from sagittarius_engine.extensions.pyside_mvc import (
    configure_app_qml,
    get_theme_bridge,
)


def seed_app_theme() -> None:
    """Registers this app's palette and icons for both rendering paths.

    Idempotent: `configure_app_qml()` replaces its stored config, and
    `get_theme_bridge()` returns the already-built singleton after the first
    call, so a process that calls this twice (a test fixture plus the
    bootstrapper it exercises) is fine.
    """
    configure_app_qml(
        Palette.as_ui_dict(),  # type: ignore[arg-type]
        get_icon_loader(),
        Palette.as_icon_dict(),
    )
    get_theme_bridge(Palette.as_ui_dict())  # type: ignore[arg-type]
