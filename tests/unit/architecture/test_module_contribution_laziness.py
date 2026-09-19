"""`contribute()` imports no widget module, and calls no factory.

**The check `test_module_declarations.py`'s own docstring has promised since
PR 0.2, and that nobody wrote.** That file says "checked by a `sys.modules`
snapshot in `test_module_contribution_laziness`"; no such file existed until
`EPIC-025` PR 1.4c-4 gave the rule its first subject — `trading`'s Dev Board
probe, the first contribution any module makes.

**Why the rule.** `contribute()` runs at boot for every run, including a
headless `sync` that never opens a window, and it runs *before* any surface
decides to render. Two things follow, and both are what this guard holds:

1. **No widget module is imported.** A `QWidget` subclass imported at
   contribute time costs every headless run the Qt import it does not need,
   and it is the first step of the drift that ends with a module building its
   panels at boot.
2. **No factory is called.** The descriptor's whole point is that the shell
   decides *when* — a factory called here would build a widget before a
   `QApplication` exists in a headless run, and before the surface that will
   place it exists in a GUI one.

Both are checked against the real `MODULES`, with a registry that records
instead of rendering.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.contribution_descriptor import (
    ContributionDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_registry import (
    IContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from Sagittarius_Elite_Warrior.src.shell.modules import MODULES

#: The directory `Sagittarius_Elite_Warrior` is importable from — the
#: subprocess below needs the same import root the gate runs pytest with.
_REPO_PARENT = Path(__file__).resolve().parents[4]

#: A module under one of these is a widget module: importing it at contribute
#: time is what this guard forbids. `ui/` is the whole sub-package because a
#: module's widgets live there by HLD §6.1, and `presentation.ui` is the legacy
#: tree's own — a module may not import it at all, but a *factory* module that
#: did would fail here first, with a message about laziness rather than about
#: boundaries.
_WIDGET_PACKAGE_MARKERS = (".ui.", ".ui_widgets.", "presentation.ui.")


def _stash_container_if_needed(module: object) -> None:
    """`EPIC-025F` PR 5.2: `TradingModule`/`BacktestingModule` need `boot()`
    to have stashed a container before `contribute()` runs (their
    `dashboard_screen(self._container)`/`backtest_screen(self._container)`
    calls) — this file calls `contribute()` in isolation, the same way
    `tests/unit/shell/test_screen_wiring.py` and `tests/conftest.py`'s fake
    path do, so it stashes a sentinel the same way. Any object works: this
    guard proves the factory is never *called*, only referenced, so the
    container's own resolvability is never exercised."""
    if hasattr(module, "_container"):
        module._container = object()  # type: ignore[attr-defined]


class _RecordingRegistry(IContributionRegistry):
    """Takes descriptors and gives nothing back — what a module sees."""

    def __init__(self) -> None:
        self.descriptors: list[ContributionDescriptor] = []
        self.screens: list[ScreenContribution] = []

    def contribute(self, descriptor: ContributionDescriptor) -> None:
        self.descriptors.append(descriptor)

    def contribute_screen(self, contribution: ScreenContribution) -> None:
        self.screens.append(contribution)


def _widget_modules_in(names: set[str]) -> set[str]:
    return {
        name
        for name in names
        if name.startswith("Sagittarius_Elite_Warrior.src.modules.")
        and any(marker in f"{name}." for marker in _WIDGET_PACKAGE_MARKERS)
    }


def test_contribute_imports_no_widget_module() -> None:
    before = _widget_modules_in(set(sys.modules))

    registry = _RecordingRegistry()
    for module_cls in MODULES:
        module = module_cls()
        _stash_container_if_needed(module)
        module.contribute(registry)

    new_widget_modules = _widget_modules_in(set(sys.modules)) - before
    assert not new_widget_modules, (
        "contribute() imported a widget module: "
        f"{sorted(new_widget_modules)}. The descriptor's factory must import "
        "its widget inside itself, so a headless run never pays for a panel "
        "nobody opened (see `modules/trading/ui/probes.py`)."
    )


def test_contribute_costs_a_headless_run_no_qt_import_at_all() -> None:
    """The rule's real statement, measured in a fresh interpreter.

    The in-process check above cannot see the whole truth: this test session
    has imported Qt for its own widgets long before it gets here, so a
    `PySide6` already in `sys.modules` proves nothing. A subprocess that does
    the boot path and nothing else does prove it — import the module list,
    contribute, and ask whether Qt got pulled in. That is exactly what a
    headless `sync` does, and the number it must pay is zero.
    """
    script = textwrap.dedent(
        """
        import sys

        from Sagittarius_Elite_Warrior.src.shell.modules import MODULES


        class Registry:
            def contribute(self, descriptor):
                pass

            def contribute_screen(self, contribution):
                pass


        registry = Registry()
        for module_cls in MODULES:
            module = module_cls()
            if hasattr(module, "_container"):
                module._container = object()
            module.contribute(registry)

        qt = sorted(name for name in sys.modules if name.startswith("PySide6"))
        print(";".join(qt))
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPO_PARENT,
    )

    imported_qt = [name for name in completed.stdout.strip().split(";") if name]
    assert not imported_qt, (
        "contribute() pulled Qt into a headless run: "
        f"{imported_qt}. The descriptor's factory must import its widget "
        "inside itself (see `modules/trading/ui/probes.py`)."
    )


def test_the_modules_that_contribute_are_the_ones_that_say_they_do() -> None:
    """A module with no UI implements nothing and contributes nothing; the
    guard would otherwise pass vacuously the day every module stops
    contributing, which is exactly when it stops being able to fail."""
    registry = _RecordingRegistry()
    for module_cls in MODULES:
        module = module_cls()
        _stash_container_if_needed(module)
        module.contribute(registry)

    contributors = {descriptor.contributor_id for descriptor in registry.descriptors}
    assert contributors == {"trading", "market_data"}, (
        "The set of contributing modules changed. That is allowed — update "
        "this assertion in the same commit, so the guard keeps a subject."
    )
