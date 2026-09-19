"""
Root conftest.py — shared fixtures available to all tests.
"""

from collections.abc import Mapping
from typing import Any
from unittest.mock import Mock

import pytest


@pytest.fixture(scope="session", autouse=True)
def _seed_app_theme():
    """Stands in for the bootstrapper, once per session.

    Every widget this suite builds directly — `SettingsView`, `DashboardView`,
    `DataManagementView`, `Sidebar`, any `kit` role — needs the app's theme
    registered before construction, and tests bypass
    `app_bootstrapper.build()` where that normally happens. So this fixture
    makes the same call the bootstrapper makes, with the real
    `Palette`/`IconLoader`, so tests exercise the real wiring.

    It calls `seed_app_theme()` rather than spelling out the engine's
    `configure_app_qml()` + `get_theme_bridge(palette)` pair, which is what it
    used to do: `BOT-133` made that one function precisely so a seventh copy
    could not drift, and `test_quick_widget_only_in_embed.py` now holds `tests/`
    to the same rule as `src/` and `scripts/`.

    Note what the second half of that pair buys here, because it is not
    obvious: it primes the theme-bridge singleton, which is otherwise lazy
    (first built inside `create_quick_widget()`). Some tests call
    `get_theme_bridge()` with no palette, which only works once the singleton
    exists — and test execution order is not guaranteed.

    The import stays inside the function on purpose: at module scope it would
    pull PySide6 and the engine into collection for every test in the
    repository, UI or not.
    """
    from Sagittarius_Elite_Warrior.src.support.ui_kit.theme_bootstrap import (
        seed_app_theme,
    )

    seed_app_theme()


def real_screen_registry(container):
    """`EPIC-016` — a `ScreenRegistry` with the app's real screens
    registered against `container`, matching exactly what
    `app_bootstrapper.py`'s composition root does.

    Since `EPIC-025` PR 1.5a that includes the shell's own **Welcome**
    screen, which is the default route (ADR D13). Leaving it out here made
    every caller of this helper fail with "no ScreenModule declared
    is_default=True" the moment the Dev Board stopped claiming it — the
    helper's promise is to match the real registry, so it follows.

    Plain function, not a fixture: `test_composition_root.py` needs this at
    collection time (inside `@pytest.mark.parametrize`'s argument list),
    before pytest fixtures are available to call. `container` may be a real
    `IContainer` or a `Mock` — nothing here resolves anything from it until
    a screen's own `view_factory`/`presenter_factory` runs, which stays lazy
    exactly like `PresenterManager` itself.

    `EPIC-025F` PR 5.2 — every screen (the shell's Welcome/Settings, and
    every module's own, the last four converting in this pull request) now
    arrives through `assemble_contributions()`, the same single function
    `app_bootstrapper.py`'s composition root calls. A real `IContainer` gets
    that call, for the same "why here and not in create_app()" reason
    `shell/contribution_assembly.py`'s own docstring gives; a `Mock()`
    cannot — `assemble_contributions()` reads `RegisteredModules` off the
    container, which a bare `Mock()` cannot answer meaningfully — so it
    builds the same contributions by calling each real module's own
    `contribute()` directly, skipping only the `register()`/`boot()` steps a
    `Mock()` has no real graph to run.
    """
    from unittest.mock import Mock

    from Sagittarius_Elite_Warrior.src.shell.screen_wiring import build_screen_registry

    if not isinstance(container, Mock):
        from Sagittarius_Elite_Warrior.src.shell.contribution_assembly import (
            assemble_contributions,
        )

        contributions = assemble_contributions(container, dev_mode=False)
        return build_screen_registry(contributions)

    from Sagittarius_Elite_Warrior.src.modules.backtesting.module import (
        BacktestingModule,
    )
    from Sagittarius_Elite_Warrior.src.modules.market_data.module import (
        MarketDataModule,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.module import TradingModule
    from Sagittarius_Elite_Warrior.src.shell.contribution_registry import (
        ContributionRegistry,
    )
    from Sagittarius_Elite_Warrior.src.shell.settings.settings_screen import (
        settings_screen,
    )
    from Sagittarius_Elite_Warrior.src.shell.welcome.welcome_screen import (
        welcome_screen,
    )

    contributions = ContributionRegistry(dev_mode=False)
    contributions.contribute_screen(welcome_screen())
    contributions.contribute_screen(settings_screen())
    trading_module = TradingModule()
    trading_module._container = container
    backtesting_module = BacktestingModule()
    backtesting_module._container = container
    for module in (MarketDataModule(), trading_module, backtesting_module):
        module.contribute(contributions)
    return build_screen_registry(contributions)


@pytest.fixture(scope="session")
def qapp():
    """
    Session-scoped QApplication fixture for PySide6 tests.
    A single QApplication instance must exist for the entire test session.
    Creates one if PySide6 is available; skips the test if not installed.
    """
    try:
        import sys

        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        yield app
    except ImportError:
        pytest.skip("PySide6 not installed — skipping UI tests")


# ---------------------------------------------------------------------------
# QML test helpers
#
# QML items created by a Repeater are NOT QObject-children of the QML root, so
# `rootObject().findChild(...)` never finds them (verified empirically while
# building the QML sidebar). They ARE reachable through the *visual* tree, so
# these walk `childItems()` instead.
# ---------------------------------------------------------------------------


def walk_qml_items(item):
    """Yields every descendant of a QQuickItem via the visual child tree."""
    for child in item.childItems():
        yield child
        yield from walk_qml_items(child)


def find_qml_item(root_item, object_name: str):
    """
    @brief Finds a QML item by its `objectName`, searching the visual tree.
    @returns The item, or None when no descendant carries that objectName.
    """
    for child in walk_qml_items(root_item):
        if child.objectName() == object_name:
            return child
    return None


def find_all_named(root_item, prefix: str):
    """
    @brief Finds every descendant of `root_item` whose `objectName` starts
    with `prefix`, searching the visual tree — for a `Repeater`'s rows, which
    all share one prefix (e.g. `selectItem_0`, `selectItem_1`, ...).
    @returns A list of matching items, in tree order, possibly empty.

    Always re-call this after any signal that can trigger a `Repeater` model
    rebuild (`rowsChanged`/`optionsChanged`/`cardsChanged`) rather than
    reusing items from a previous call — a `QVariantList` model rebuilds its
    delegates wholesale on every change (measured: the Python id of a
    `CheckBox` before and after a `rowsChanged` differ), so an item held
    across a refresh is a reference to a destroyed `QQuickItem`.
    """
    return [
        child
        for child in walk_qml_items(root_item)
        if child.objectName() and child.objectName().startswith(prefix)
    ]


@pytest.fixture
def qml_item():
    """
    Provides `find_qml_item` to tests.

    Usage:
        button = qml_item(view.quick_widget.rootObject(), "navButton_dashboard")
        button.clicked.emit()
    """
    return find_qml_item


# --------------------------------------------------------------------- #
# One fake DI container for Presenter tests
#
# Twenty-six test modules each hand-rolled the same object: a `Mock()`
# whose `resolve` is an `if interface is X: return y` ladder ending in
# `return Mock()`. Not twenty-six fakes — one mechanism copied, and the
# copies made adding a Presenter dependency cost one edit per module.
#
# This session hit that twice (`TradingSessionState`, `LiveStrategySession`)
# and the second time did worse than break tests: the ladders end in
# `Mock()`, so an un-taught container answered `session_state.enabled`
# with a truthy `Mock` and the tests kept passing while exercising the
# wrong branch. A shared fake does not remove that hazard, but it puts the
# fallback in one reviewable place instead of twenty-six.
#
# Not the real container: that one auto-wires, so it would build real
# infrastructure inside a unit test. Answering `Mock()` for the
# uninteresting collaborators is the point.
# --------------------------------------------------------------------- #


def fake_container(bindings: Mapping[Any, Any] | None = None, **extra: Any) -> Mock:
    """@brief A container that resolves `bindings` and mocks the rest.

    @param bindings Interface/class -> instance. Matched by identity
    first, then by class name — some test modules import `IConfig` from a
    different path than the code under test does, which an `is` check
    alone silently misses (that is why several of the hand-rolled ladders
    carried an `interface.__name__ == "IConfig"` branch).
    @param extra Convenience for the common one-off:
    `fake_container(config=cfg)` binds by attribute name rather than
    needing the class imported.

    @returns A `Mock` with `resolve` wired up — still a `Mock`, so a test
    that wants to assert on resolution order can.
    """
    by_identity = dict(bindings or {})
    by_name = {
        getattr(key, "__name__", str(key)): value for key, value in by_identity.items()
    }
    by_name.update(extra)
    #: Remembered so repeated resolutions of the same unbound interface
    #: hand back the SAME mock. A fresh one per call quietly breaks any
    #: test that resolves twice and expects one object — which is what
    #: production code does whenever two collaborators share a service.
    invented: dict[Any, Mock] = {}

    def resolve(interface: Any) -> Any:
        if interface in by_identity:
            return by_identity[interface]
        name = getattr(interface, "__name__", None)
        if name is not None and name in by_name:
            return by_name[name]
        return invented.setdefault(interface, Mock())

    container = Mock()
    container.resolve.side_effect = resolve
    return container


@pytest.fixture
def make_container():
    """Factory fixture around `fake_container` — `make_container({IConfig: cfg})`."""
    return fake_container


#: Importable by the test modules that build a Presenter.
__all__ = ["fake_container", "make_container"]
