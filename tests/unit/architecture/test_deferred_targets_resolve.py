"""Every `Deferred` factory the real modules contribute resolves, and stays home.

**Why this guard exists.** `Deferred` (`src/core/contracts/deferred.py`) names a
factory by its import path so `contribute()` imports no widget module, without
a function-local import per factory. A path is a string: mypy cannot see a
typo, and the import guards cannot see where it points. This file is what can.
It walks the contributions every module in `MODULES` makes and, for each
`Deferred` factory, checks two things:

1. the target imports and names something callable. Without this, a typo
   would surface only when someone opens the screen;
2. the target lives inside the contributing module's own package. A module
   may build only its own widgets, as `test_module_boundaries.py` holds for
   real imports.

Retire when: no contribution uses `Deferred`, or Python's own lazy imports
(PEP 810) replace it with statically checked imports.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.contribution_descriptor import (
    ContributionDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_registry import (
    IContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.options_page_contribution import (
    OptionsPageContribution,
)
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from Sagittarius_Elite_Warrior.src.shell.modules import MODULES


class _RecordingRegistry(IContributionRegistry):
    """Notes each module's contributions under the module's package."""

    def __init__(self) -> None:
        self.package = ""
        self.deferred: list[tuple[str, Deferred[object]]] = []

    def contribute(self, descriptor: ContributionDescriptor) -> None:
        self._note(descriptor.factory)

    def contribute_screen(self, contribution: ScreenContribution) -> None:
        self._note(contribution.view_factory)
        self._note(contribution.presenter_factory)

    def contribute_options_page(self, contribution: OptionsPageContribution) -> None:
        self._note(contribution.factory)

    def _note(self, factory: object) -> None:
        if isinstance(factory, Deferred):
            self.deferred.append((self.package, factory))


def _contributed() -> list[tuple[str, Deferred[object]]]:
    registry = _RecordingRegistry()
    for module_cls in MODULES:
        module = module_cls()
        if hasattr(module, "_container"):
            module._container = object()  # type: ignore[attr-defined]
        registry.package = module_cls.__module__.rpartition(".")[0]
        module.contribute(registry)
    return registry.deferred


def test_the_guard_has_a_subject() -> None:
    assert _contributed(), "no module contributes a Deferred factory any more"


def test_every_deferred_target_imports_and_is_callable() -> None:
    broken = []
    for _, factory in _contributed():
        try:
            target = factory.resolve()
        except (ImportError, AttributeError) as exc:
            broken.append(f"{factory.target}: {exc}")
            continue
        if not callable(target):
            broken.append(f"{factory.target}: not callable")
    assert not broken, "Deferred targets that do not resolve:\n" + "\n".join(broken)


def test_every_deferred_target_lives_in_its_contributing_module() -> None:
    strays = [
        f"{package} contributes {factory.target}"
        for package, factory in _contributed()
        if not factory.module.startswith(f"{package}.")
    ]
    assert not strays, "a module may defer only to its own package:\n" + "\n".join(
        strays
    )


def test_a_target_without_module_and_attribute_is_refused() -> None:
    for bad in ("no_colon", ":attribute", "module:"):
        try:
            Deferred(bad)
        except ValueError:
            continue
        raise AssertionError(f"Deferred accepted {bad!r}")
