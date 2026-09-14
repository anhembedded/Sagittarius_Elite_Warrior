"""Registering the bounded contexts, in the list's order (SDD boot steps 3–5).

`shell/modules.py` is the source of truth for which contexts exist and in what
order — not the Engine's dependency sort, because `contribute()` runs in this
order and that order is visible in the UI. This function is where the list turns
into `app.use()` calls, with both `register()` rules enforced as each module goes
in:

- every claim goes through a `RegisteringContainer`, so a `resolve()` during
  `register()` fails immediately and says which module did it;
- every claim is recorded, so the second module to claim a type fails **before**
  `boot()` rather than silently winning.

The container swap is temporary and per module: the Engine's `App.use()` calls
`register()` synchronously, so the spy is installed, the module registers
through it, and the real container is restored before the next module — nothing
outside this function ever sees the spy.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.shell.double_claim_check import DoubleClaimCheck
from Sagittarius_Elite_Warrior.src.shell.registering_container import (
    RegisteringContainer,
)
from sagittarius_engine import App


def register_modules(
    app: App, modules: Iterable[type[BoundedContextModule]]
) -> tuple[Sequence[BoundedContextModule], DoubleClaimCheck]:
    """`app.use()` every module in list order, spying on each `register()`."""
    check = DoubleClaimCheck()
    registered: list[BoundedContextModule] = []
    real_container = app.context.container

    for module_cls in modules:
        module = module_cls()
        spy = RegisteringContainer(real_container, module.module_id)
        app.context.container = spy
        try:
            app.use(module)
        finally:
            app.context.container = real_container
        check.record(module.module_id, spy.claims())
        registered.append(module)

    return tuple(registered), check
