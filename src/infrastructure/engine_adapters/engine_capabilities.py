"""What this app needs the *installed* `sagittarius_engine` build to provide.

@par The failure this closes
`sagittarius_engine` is a separate repository installed into the venv, not a
submodule pinned by commit (`ONBOARDING.md` §2). So the app's source and the
engine's build drift independently, and an app that calls an engine API added
last week fails on a machine whose venv still holds last month's engine.

That failure has a signature which reliably misleads: `AttributeError`,
`TypeError: unexpected keyword argument`, or `Can't instantiate abstract
class`, raised deep inside a widget constructor. `install-rule.md` §1 records
three occurrences — `BUG-044`, `BUG-054`, `BUG-055` — every one of them
initially diagnosed as *"the app references an API that does not exist"* when
the API existed upstream and only the installed build was stale. `pip show`
does not help: current and outdated builds both report the same version.

`BOT-132` produced the fourth: `create_quick_widget(background=...)` raised
`TypeError` in `PositionsPanel.__init__` during boot, on an app checkout that
was correct and an engine build that was old.

@par The rule this file encodes
**An engine API this app depends on is declared here, not discovered by
crashing.** `EngineCapabilityValidatorExtension` checks every entry at boot
and fails with the reinstall command, so the diagnosis is the error message.

@par Adding one is a single line
When a change starts depending on a newly added engine API, add a
`RequiredEngineCapability` naming the symbol, the parameter (if the
dependency is on a parameter rather than the symbol), and the task that
introduced it. That declaration is what makes the next stale-build failure
self-explaining; nothing else has to be written anywhere.

Keep this list to APIs whose *absence* is plausible — recently added, or
recently given a new parameter. It is not an inventory of everything the app
imports: a symbol that has existed for a year fails loudly enough on its own,
and a list nobody can keep true is worse than no list (`ONBOARDING.md`'s
standing complaint about hand-maintained copies of state).
"""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass

#: The command that fixes every failure this module reports — `install-rule.md`
#: §1, Option 1. `--force-reinstall` is load-bearing: pip considers the same
#: version already satisfied and would otherwise do nothing, which is exactly
#: how a stale build survives a reinstall attempt.
REINSTALL_COMMAND = (
    "pip install --upgrade --force-reinstall "
    "git+https://github.com/anhembedded/Sagittarius_Engine.git"
)


@dataclass(frozen=True)
class RequiredEngineCapability:
    """One engine API this app's current source depends on.

    @param module Dotted module path, e.g. `sagittarius_engine.extensions.pyside_mvc`.
    @param attribute Symbol inside it, e.g. `create_quick_widget`.
    @param parameter Optional parameter name the app passes. Declare this when
        the dependency is on a *signature*, not merely on the symbol existing —
        an older build that has the function but not the parameter is the case
        that raises `TypeError: unexpected keyword argument`.
    @param since Task/bug id that introduced the dependency, quoted back in the
        failure so a reader can find out what it is for.
    """

    module: str
    attribute: str
    parameter: str | None = None
    since: str = ""

    def describe(self) -> str:
        target = f"{self.module}.{self.attribute}"
        if self.parameter is not None:
            target = f"{target}(..., {self.parameter}=...)"
        return f"{target} [{self.since}]" if self.since else target


#: Declared dependencies on recently added engine APIs. See the module
#: docstring for when to add one, and for why this list is deliberately short.
REQUIRED_ENGINE_CAPABILITIES: tuple[RequiredEngineCapability, ...] = (
    # BOT-132/BUG-115: every embedded QML scene clears to an opaque token
    # colour. Without this parameter the app cannot construct a single QML
    # widget — it raised `TypeError` inside `PositionsPanel` at boot.
    RequiredEngineCapability(
        module="sagittarius_engine.extensions.pyside_mvc",
        attribute="create_quick_widget",
        parameter="background",
        since="TASK-042 (engine) / BOT-132 (app)",
    ),
    # EPIC-025F PR 5.3: shell/contribution_registry.py's panel half is
    # rebuilt on this class rather than a hand-rolled copy of its logic.
    RequiredEngineCapability(
        module="sagittarius_engine.extensions.pyside_mvc.runtime.contribution_registry",
        attribute="ContributionRegistry",
        since="TASK-043 E1 (engine) / EPIC-025F PR 5.3 (app)",
    ),
)


def find_missing_capabilities(
    capabilities: tuple[RequiredEngineCapability, ...] = REQUIRED_ENGINE_CAPABILITIES,
) -> list[str]:
    """Returns a human-readable line per capability the installed engine lacks.

    @details Import errors, missing attributes and missing parameters all
    reduce to the same answer for the operator — the installed build is too
    old — so they produce one uniform list rather than three error types.
    Empty list means the installed engine satisfies everything declared.
    """
    missing: list[str] = []
    for capability in capabilities:
        try:
            module = importlib.import_module(capability.module)
        except ImportError:
            missing.append(f"{capability.describe()} — module not importable")
            continue

        target = getattr(module, capability.attribute, None)
        if target is None:
            missing.append(f"{capability.describe()} — attribute missing")
            continue

        if capability.parameter is None:
            continue

        try:
            signature = inspect.signature(target)
        except (TypeError, ValueError):  # pragma: no cover - builtins/C objects
            missing.append(f"{capability.describe()} — signature unreadable")
            continue

        if capability.parameter not in signature.parameters:
            missing.append(
                f"{capability.describe()} — parameter "
                f"{capability.parameter!r} missing from {signature}"
            )
    return missing


def format_missing_capabilities(missing: list[str]) -> str:
    """The operator-facing report: what is stale, and the one command to fix it."""
    lines = "\n".join(f"    - {entry}" for entry in missing)
    return (
        "CRITICAL FAULT: the installed `sagittarius_engine` build is older than "
        "this app's source.\n"
        "The following engine APIs this app depends on are missing:\n"
        f"{lines}\n\n"
        "This is not a bug in the app — see install-rule.md §1 "
        "(BUG-044/BUG-054/BUG-055 were all this).\n"
        "Fix by reinstalling the engine:\n"
        f"    {REINSTALL_COMMAND}\n"
        "If the change you need lives on an engine branch that is not merged "
        "yet, append `@<branch-name>` to that URL."
    )
