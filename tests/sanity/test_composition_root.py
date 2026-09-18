"""
Sanity tier — the composition root, proven by scanning rather than by listing.

The tier's subject is not "the app". It is what production actually assembles:

    Composition root = Graph(nodes, edges) + Lifecycle(enter, exit) + EntryPoints

and its question is: *can that come into existence at all, and does it assemble
in silence?* Not "is it correct" (Unit), not "does the user get what they
wanted" (Integration), not "what is on screen" (Desktop E2E).

Every test here scans a real source of truth. None of them names a screen, a
strategy, a command or a symbol — because an assertion that needs editing when a
feature changes does not belong in this tier, and because a hand-written list can
only catch a deletion somebody remembered to make. The failure that actually
happens is the opposite one: something added and never registered.

The design consequence worth measuring: **adding a feature must add zero tests to
this file.** If a new screen ever requires a new sanity test, the tests here were
written wrong. `.claude/skills/test-health/` escalates when this file grows.

Model, decisions and open questions: `Tasks/epics/EPIC-009_sanity_tier_redesign/`.
The seven retired modules are kept for test-case reference at
`Tasks/reference/sanity_legacy/` and are deliberately outside any collected path.

NOT VERIFIED. Authored where PySide6 and `sagittarius_engine` cannot be
installed, so not one line has been executed. Several failures are expected on
the first real run, and each answers an open question in the ADR rather than
indicating a broken test — see the note on each.
"""

from __future__ import annotations

import importlib
import inspect
import threading
import time
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_PKG = "Sagittarius_Elite_Warrior.src"

#: Seconds the whole application is allowed to take to shut down. Generous on
#: purpose: this asserts "it terminates", not "it terminates quickly". ADR Q7.
_SHUTDOWN_BUDGET_SECONDS = 10.0

#: Use-case classes that legitimately resolve to nothing — abstract bases, DTOs
#: that are never dispatched. Every entry needs a written reason. Expected to be
#: populated once, from the first real run, and then to stay still.
_NOT_DISPATCHED: set[str] = {
    # `EPIC-021F`: `ITradingClient` is registered only when `TradingVenue !=
    # DISABLED` (ADR §3 — trading is opt-in, never on by config omission).
    # This fixture boots with production's own default config, where it is
    # `DISABLED`, so `SubmitOrderCommand` genuinely cannot resolve here — not
    # because it is never dispatched (`order-dry-run` dispatches it for
    # real), but because this specific boot has trading turned off, same as
    # any real install until someone opts in.
    "SubmitOrderCommand",
}


def _import_all_under(relative_dir: str):
    """Imports every module under `src/<relative_dir>` and yields them.

    Import is the point, not a side effect: a module that cannot be imported is
    itself a composition failure, and this is the tier that should say so.
    """
    root = _SRC / relative_dir
    for path in sorted(root.rglob("*.py")):
        if path.name.startswith("_"):
            continue
        dotted = ".".join((_PKG, *path.relative_to(_SRC).with_suffix("").parts))
        yield importlib.import_module(dotted)


def _use_case_roots() -> tuple[str, ...]:
    """Every tree this application keeps use cases in, read from disk.

    **Derived, not listed, and that is the whole point.** This scan read
    `application/use_cases` alone from PR 0.2 until PR 2.1b, while `EPIC-025`
    moved three contexts out from under it — so it was checking **4** of the
    **26** `Command`/`Query` classes the app has, and `checked > 0` kept it
    green the whole time. Measured on the tree that found it: 4 in the legacy
    root, 11 in `market_data`, 9 in `trading`, 2 in `strategy`.

    Listing the module roots here would have the same failure one phase later,
    when Phase 3 brings `backtesting`. Reading `src/modules/*/application` off
    disk means a module cannot be forgotten, and `_MINIMUM_USE_CASES_CHECKED`
    below is what turns a *narrowing* — the shape that actually happens — into a
    failure rather than a smaller silent pass.

    **PR 3.1c: the legacy root is gone from this tuple, and that prediction came
    true one phase early.** `backtesting` arrived and took `application/
    use_cases/backtest` with it, which left `src/application/` **empty** — so
    the hard-coded first element became a root with nothing in it. Deriving the
    module roots is what kept the scan honest through that; the one written-down
    entry is the one that had to be deleted by hand.
    """
    modules_root = _SRC / "modules"
    return tuple(
        sorted(
            f"modules/{package.name}/application"
            for package in modules_root.iterdir()
            if package.is_dir()
            and not package.name.startswith("_")
            and (package / "application").is_dir()
        )
    )


#: A floor, not a count: it moves with every use case added and a ratchet on it
#: would be noise. Chosen so that seeing only one module's tree fails — which is
#: the exact regression above. The legacy tree it also used to guard against is
#: gone: PR 3.1c emptied `src/application/` entirely.
_MINIMUM_USE_CASES_CHECKED = 20

#: Where the strategy implementations live. `EPIC-025` PR 2.1b moved them from
#: `domain/strategies` into the module that owns them; the constant has to
#: follow, and this one was caught by the gate rather than by reading, because
#: the count on the other side of its assertion is read from the real registry.
_STRATEGIES_ROOT = "modules/strategy/domain/strategies"


def _classes_defined_in(module, suffix: str) -> list[type]:
    """Classes whose name ends with `suffix` and that this module actually
    defines — re-exports would otherwise be counted several times over."""
    return [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if obj.__name__.endswith(suffix)
        and obj.__module__ == module.__name__
        and not obj.__name__.startswith(("Base", "Abstract", "I"))
    ]


# ---------------------------------------------------------------------------
# Graph — modes 1, 3, 4, 5
# ---------------------------------------------------------------------------


def test_every_use_case_resolves_to_a_handler(booted_app):
    """Mode 5 — in source, not in the graph.

    Replaces two hand-maintained `parametrize` allowlists (`_BACKTEST_COMMANDS`,
    `_DATABASE_COMMANDS`, kept for reference under `Tasks/reference/`). Those
    caught a handler *removed* from `binance_bot_module.py` and were structurally
    blind to one that was never added — which is the direction real regressions
    travel.

    Every use case resolves without touching the network, including the three
    that depend on `PythonBinanceClient` — `conftest.py`'s `booted_app` points
    the real `Client` at `EPIC-009` D6's local fake Binance server rather than
    mocking `IExchangeClient` itself, so this closed `BUG-045` (the DI graph
    reaching `api.binance.com` merely by being resolved) without introducing a
    hand-written substitute for the port to fall behind, the way `BUG-026` and
    `BUG-027` did.
    """
    container = booted_app.context.container

    unresolved: list[str] = []
    checked = 0
    for root in _use_case_roots():
        for module in _import_all_under(root):
            for cls in _classes_defined_in(module, "Command") + _classes_defined_in(
                module, "Query"
            ):
                if cls.__name__ in _NOT_DISPATCHED:
                    continue
                checked += 1
                try:
                    if container.resolve(cls) is None:
                        unresolved.append(f"{cls.__module__}.{cls.__name__} -> None")
                except Exception as exc:  # noqa: BLE001 - the failure is the finding
                    unresolved.append(f"{cls.__module__}.{cls.__name__} -> {exc!r}")

    assert checked >= _MINIMUM_USE_CASES_CHECKED, (
        f"only {checked} Command/Query classes were checked across "
        f"{list(_use_case_roots())}, which is fewer than this application has. A "
        "scan that has lost part of its subject does not fail, it passes faster — "
        "this one read the legacy tree alone for three phases while the contexts "
        "moved out from under it. Find the tree it is no longer reading."
    )
    assert unresolved == [], (
        f"{len(unresolved)} of {checked} use cases do not resolve through the "
        f"real container — check binance_bot_module.py:\n  " + "\n  ".join(unresolved)
    )


def test_every_strategy_on_disk_is_registered(booted_app):
    """Mode 5, for the strategy registry.

    Replaces four tests that each pinned one hard-coded strategy name to one BOT
    number — a set that grew with every strategy and proved less each time.

    Counts rather than names, deliberately: the registry key (`ema_crossover`) is
    not derivable from the class (`EmaCrossoverStrategy`), and inventing a
    mapping would put business knowledge back into this tier. A count mismatch
    still catches the regression that matters — a strategy added and never
    registered — and the message names both sides.
    """
    from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
        StrategyRegistry,
    )

    on_disk = [
        cls.__name__
        for module in _import_all_under(_STRATEGIES_ROOT)
        for cls in _classes_defined_in(module, "Strategy")
    ]
    registered = sorted(
        booted_app.context.container.resolve(StrategyRegistry).available()
    )

    assert on_disk, (
        f"no strategy class found under src/{_STRATEGIES_ROOT}. The equality "
        "below would then read 0 == 0 the day the registry is empty too, so this "
        "says it out loud instead: the scan root moved, and `_STRATEGIES_ROOT` "
        "did not follow."
    )
    assert len(on_disk) == len(registered), (
        f"{len(on_disk)} strategy implementations on disk but {len(registered)} "
        f"registered — one was added without registering it, or a registration "
        f"outlived its class.\n  on disk:    {sorted(on_disk)}\n  registered: {registered}"
    )


# ---------------------------------------------------------------------------
# Entry points — modes 11 and 12
# ---------------------------------------------------------------------------


def _navigable_routes() -> list[str]:
    """Every route a user can actually reach, read from the real
    `ScreenRegistry` (`EPIC-016`) — not from a list maintained here.

    A throwaway `Mock()` container is enough: nothing here calls
    `create_view()`/`create_presenter()`, only `build_descriptor()`'s
    nav-metadata construction, which never touches the container.
    """
    from unittest.mock import Mock

    from Sagittarius_Elite_Warrior.tests.conftest import real_screen_registry

    registry = real_screen_registry(Mock())
    return [d.route for d in registry.get_all() if d.has_nav()]


def _screen_packages() -> list[str]:
    """Dormant, not deleted — `EPIC-025` Phase 4 moved every screen out of
    this tree (settings, the last one, in PR 4.4e), so it no longer exists
    on disk and this always returns `[]` now.
    `Tasks/backlog/BOT-141_retarget_event_flow_guard_3_to_module_ui.md` is
    the follow-up that retargets this check to `modules/*/ui/`/`shell/`."""
    screens_root = _SRC / "presentation" / "ui" / "screens"
    if not screens_root.is_dir():
        return []
    return sorted(
        d.name
        for d in screens_root.iterdir()
        if d.is_dir() and not d.name.startswith(("_", "."))
    )


@pytest.mark.parametrize("route", _navigable_routes())
def test_every_navigable_route_constructs(qapp, booted_app, route):
    """Mode 11 — an entry point that is registered but cannot be built.

    The retired tier constructed two of four screens: `PresenterManager` is
    lazy-loading and `MainWindow.__init__` only navigates to `dashboard`, so the
    Database and Settings screens were never built by any sanity test. BUG-019
    (a Database-screen modal that could not construct) landed in exactly that gap.

    Parametrised from the navigation constants themselves, so a screen added
    later is covered without editing this file.

    First-run note: this is where ADR Q3 gets answered — whether `MainWindow`
    constructs under `offscreen` *with* the full theme/font/theme-bridge
    bootstrap, which the retired tier never exercised.
    """
    from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
    from Sagittarius_Elite_Warrior.src.support.ui_kit.sidebar import Sidebar
    from Sagittarius_Elite_Warrior.tests.conftest import real_screen_registry

    registry = real_screen_registry(booted_app.context.container)
    window = MainWindow(booted_app, registry, sidebar_factory=Sidebar)
    try:
        window.switch_screen(route)
        qapp.processEvents()

        assert window._stacked.currentWidget() is not None, (
            f"Route '{route}' navigated but left no widget on the stack — the "
            f"view was constructed and then orphaned."
        )
    finally:
        window.shutdown()
        window.deleteLater()
        qapp.processEvents()


def test_every_screen_package_has_a_navigable_route():
    """Mode 12 — an entry point that exists but nothing registers.

    No bug has ever exercised this, which is the whole argument for deriving the
    failure list from the structure of the composition root rather than from the
    bug history: a screen package that was never given a `*ScreenModule`
    registered in `app_bootstrapper.py` (`EPIC-016`) is unreachable to every
    other test in the suite, including the one directly above.

    The scanning technique is already proven in this repo —
    `tests/unit/presentation/ui/test_preview_fixtures_exist.py` walks the same
    directory to enforce the `preview.py` convention. It was simply never applied
    to routes.

    Needs no app boot, so it stays cheap.
    """
    unrouted = sorted(set(_screen_packages()) - set(_navigable_routes()))

    assert unrouted == [], (
        f"Screen package(s) on disk that no navigation entry points at, so no "
        f"user and no test can reach them: {unrouted}. Either give them a "
        f"`*ScreenModule` registered in app_bootstrapper.py, or delete them."
    )


# ---------------------------------------------------------------------------
# Lifecycle — modes 9 and 10 (in-process approximation)
# ---------------------------------------------------------------------------


def test_the_window_shuts_down_within_budget(qapp, booted_app):
    """Modes 9 and 10, as far as an in-process test can reach them.

    Three shutdown bugs — BUG-007, BUG-023, BUG-041, two of them P1 — were all
    reported by a person closing the window and watching the process refuse to
    die. No tier watched for it: the retired fixtures called `app.stop()` in
    teardown with no assertion, so a hang surfaced as a *hung test run* rather
    than a failure, which is strictly worse than no coverage.

    Honest limitation: this cannot prove mode 9 proper. Inside pytest,
    `shutdown()` returning is not the same as the process dying, because pytest's
    process keeps living — surviving threads are a proxy for the real symptom.
    Only the out-of-process layer (ADR D2/D2b) can assert on a real exit code,
    and that is why the ADR splits the tier in two.
    """
    from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
    from Sagittarius_Elite_Warrior.src.support.ui_kit.sidebar import Sidebar
    from Sagittarius_Elite_Warrior.tests.conftest import real_screen_registry

    before = {t.ident for t in threading.enumerate()}

    registry = real_screen_registry(booted_app.context.container)
    window = MainWindow(booted_app, registry, sidebar_factory=Sidebar)
    qapp.processEvents()

    started = time.monotonic()
    window.shutdown()
    qapp.processEvents()
    elapsed = time.monotonic() - started

    window.deleteLater()
    qapp.processEvents()

    assert elapsed < _SHUTDOWN_BUDGET_SECONDS, (
        f"MainWindow.shutdown() took {elapsed:.1f}s, over the "
        f"{_SHUTDOWN_BUDGET_SECONDS}s budget — the BUG-023/BUG-041 signature."
    )

    leaked = [
        t.name
        for t in threading.enumerate()
        if t.ident not in before and not t.daemon and t.is_alive()
    ]
    assert leaked == [], (
        f"Non-daemon thread(s) still alive after shutdown, which is what keeps "
        f"the real process from exiting: {leaked}"
    )
