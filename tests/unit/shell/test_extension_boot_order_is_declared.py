"""BOT-119 — two real boot-order constraints in `composition_root.py` used to
be encoded only as `app.use()` call order plus an English comment: swapping
the calls broke nothing that told you. Both are now a declared `dependencies`
list the engine's own topological sort (`ExtensionManager._build_and_sort`)
enforces. A declaration that merely exists proves nothing about whether the
sort actually reorders around it — so each test here registers the same
extensions in the OPPOSITE order `composition_root.py` uses and asserts the
engine still runs them correctly, which is the only way to prove the
replacement mechanism, not just its presence.
"""

from __future__ import annotations

from typing import Any

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.engine_capability_validator_extension import (
    EngineCapabilityValidatorExtension,
)
from sagittarius_engine import App
from sagittarius_engine.extensions.dependency_validator import (
    DependencyValidatorExtension,
)
from sagittarius_engine.extensions.health.health_module import HealthExtension
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


def _app() -> App:
    return App(StdLibContainer(), MemoryEventBus(None))


def test_capability_check_still_runs_after_presence_check_when_calls_are_swapped() -> (
    None
):
    """`EngineCapabilityValidatorExtension.dependencies` (composition_root.py)
    must make `DependencyValidatorExtension.boot()` run first even when
    `app.use()` registers them in the opposite order.

    Mutation check: deleting `EngineCapabilityValidatorExtension.dependencies`
    turns this red, because the engine then has nothing to sort by and keeps
    the swapped registration order (`capability`, `presence`).
    """
    calls: list[str] = []
    presence = DependencyValidatorExtension(["sys"])  # always importable
    capability = EngineCapabilityValidatorExtension()

    presence_boot, capability_boot = presence.boot, capability.boot
    presence.boot = lambda ctx: (calls.append("presence"), presence_boot(ctx))[-1]  # type: ignore[method-assign]
    capability.boot = lambda ctx: (  # type: ignore[method-assign]
        calls.append("capability"),
        capability_boot(ctx),
    )[-1]

    app = _app()
    app.use(capability)  # swapped: capability registered BEFORE presence
    app.use(presence)
    app.boot()

    assert calls == ["presence", "capability"], (
        "EngineCapabilityValidatorExtension.dependencies must force the "
        "engine's topological sort to run DependencyValidatorExtension first "
        f"even when app.use() calls are swapped — got {calls}"
    )


class _RecordsRegistration(BoundedContextModule):
    """Stands in for a real bounded context: all `HealthExtension`'s declared
    dependency needs is that `register()` ran first. Appends to the shared
    `order` list the test passes in, alongside `HealthExtension` itself, so
    both sides of the constraint land on one observable timeline."""

    order: list[str] = []  # noqa: RUF012 - shared across instances by design

    def register(self, context: Any) -> None:
        type(self).order.append(self.module_id)


class _Market(_RecordsRegistration):
    module_id = "market_data"


class _Trading(_RecordsRegistration):
    module_id = "trading"


def test_health_check_still_runs_after_domain_modules_when_calls_are_swapped() -> None:
    """`composition_root.py` sets `HealthExtension.dependencies` to every
    bounded context's `module_id` (BOT-119) because `HealthCheckQuery`'s
    container sweep only finds what a module's own `register()` already
    bound. This registers `HealthExtension` BEFORE the modules — the opposite
    of `composition_root.py`'s own order — and confirms both modules still
    register before it does.

    Mutation check: dropping the `health.dependencies` assignment turns this
    red, because `HealthExtension` then initialises immediately on `app.use()`
    instead of waiting for either module.
    """
    _RecordsRegistration.order = []
    health = HealthExtension()
    health.dependencies = ["market_data", "trading"]  # type: ignore[attr-defined]

    health_register = health.register
    health.register = lambda ctx: (  # type: ignore[method-assign]
        _RecordsRegistration.order.append("health"),
        health_register(ctx),
    )[-1]

    app = _app()
    app.use(health)  # swapped: Health registered BEFORE its declared modules
    app.use(_Market())
    app.use(_Trading())
    app.boot()

    assert _RecordsRegistration.order == ["market_data", "trading", "health"], (
        "HealthExtension.dependencies must force the engine's topological "
        "sort to run both bounded-context modules before it, even when "
        f"app.use() calls are swapped — got {_RecordsRegistration.order}"
    )
