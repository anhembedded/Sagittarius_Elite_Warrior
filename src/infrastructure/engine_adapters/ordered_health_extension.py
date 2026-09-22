"""`OrderedHealthExtension` — the engine's `HealthExtension` with a typed
`dependencies` list (`BOT-119`).

@details `HealthCheckQuery`'s container sweep (engine `health_check_query.py`)
only finds what a bounded context's own `register()` already bound, so
`HealthExtension` must boot after every one of them — a real ordering
constraint, previously kept only by writing `app.use(HealthExtension())` last
in `composition_root.py` with a comment saying so. `IExtension.descriptor`
reads `dependencies` via `getattr(self, "dependencies", [])`, so setting it as
a bare instance attribute on the engine's own `HealthExtension` would work at
runtime, but mypy cannot see an attribute the class never declares — exactly
the untyped seam `code/quality.md` §1 forbids. This subclass gives the
attribute a real annotation; every lifecycle method still runs the engine's
own implementation unchanged.
"""

from __future__ import annotations

from sagittarius_engine.extensions.health.health_module import HealthExtension


class OrderedHealthExtension(HealthExtension):
    """`HealthExtension`, plus a mypy-visible `dependencies` list."""

    def __init__(self, dependencies: list[str]) -> None:
        super().__init__()
        self.dependencies = dependencies
