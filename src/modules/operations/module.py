"""`operations` — running the application unattended (`EPIC-038`, decision D4).

**The context's one question:** *how does an operator, or a supervisor, know
this process is alive and well, and make it start and stop cleanly?* It listens
to the other contexts and is depended on by none (`DESIGN_2026-10-09_headless_operation.md`
§3).

Today it holds only what `EPIC-038G` needs: the health line's format and the
host-state vocabulary. The `run` host, preflight and `status` arrive with
`EPIC-038D`, `038F` and `038C`, and join this module's hooks then. No hook is
implemented yet but `register()`, which the base class requires, so the module
binds, boots and contributes nothing: a statement, not an omission.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)


class OperationsModule(BoundedContextModule):
    """The vocabulary of an unattended run."""

    module_id = "operations"

    #: Reads no other context's `contracts/`; checked by `test_module_declarations.py`.
    dependencies: list[str] = []  # noqa: RUF012 — the Engine reads a plain attribute

    def register(self, context: object) -> None:
        """Nothing to bind yet: the format is a pure function, not a service."""
