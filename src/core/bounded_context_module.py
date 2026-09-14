"""What a bounded context looks like from the outside (HLD §3.1, ADR D2).

A module is an Engine `IExtension` plus two seams of this application's own:

| Hook | When | What it may do |
| :--- | :--- | :--- |
| `register(context)` | first, in `MODULES` order | bind and `singleton` only — no `resolve`, no I/O, no threads, no Qt |
| `boot(context)` | after every module registered | `resolve`; start hosted services and scheduler jobs |
| `contribute(registry)` | after `boot()` | hand over descriptors; no widget module imported |
| `subscribe(bridge)` | after `contribute()` | attach event handlers for the life of the process |
| `shutdown(context)` | reverse order | release what `boot()` started |

`contribute()` and `subscribe()` default to doing nothing, so a module with no
UI and no event handlers — a CLI-only context — implements neither. `module_id`
is the identity that appears in every descriptor and in `shell/modules.py`;
`dependencies` names the modules whose `contracts/` this one imports, and the
declaration guard checks that claim against the imports actually present, in
both directions.

Why subclass `IExtension` rather than the Engine's `IModule`: `IModule.register`
receives the whole `App` (and so the temptation to reach for anything on it),
while `IExtension.register` receives the `EngineContext`. The Engine wraps an
`IModule` in a `ModuleExtensionAdapter` anyway, so this is the same mechanism
with a narrower door.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from sagittarius_engine.interfaces.i_extension import ExtensionDescriptor, IExtension

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_registry import (
        IContributionRegistry,
    )
    from sagittarius_engine.extensions.pyside_mvc import QtEventBridge


class BoundedContextModule(IExtension[Any]):
    """One bounded context, registered with the Engine as one extension."""

    #: Stable id: the package name under `modules/`, e.g. `"market_data"`.
    module_id: str = ""
    #: The `module_id`s whose `contracts/` this module imports. Surplus and
    #: shortfall both fail `test_module_declarations`.
    dependencies: list[str] = []  # noqa: RUF012 — the Engine reads this as a plain attribute

    def __init__(self) -> None:
        if not self.module_id:
            raise ValueError(f"{type(self).__name__} must declare a module_id")

    @property
    def name(self) -> str:
        return self.module_id

    @property
    def descriptor(self) -> ExtensionDescriptor:
        return ExtensionDescriptor(
            name=self.module_id,
            dependencies=list(self.dependencies),
            description=type(self).__doc__ or "",
        )

    @abstractmethod
    def register(self, context: Any) -> None:
        """Bind this context's ports to their adapters. No `resolve()`."""

    def boot(self, context: Any) -> None:
        """Start what needs a built object graph. Default: nothing."""

    def shutdown(self, context: Any) -> None:
        """Release what `boot()` started. Default: nothing."""

    def contribute(self, registry: IContributionRegistry) -> None:
        """Offer this context's panels, dialogs and screens. Default: none."""

    def subscribe(self, bridge: QtEventBridge) -> None:
        """Attach this context's long-lived event handlers. Default: none."""
