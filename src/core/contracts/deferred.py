"""A factory named by its import path, imported on its first call.

**Why.** `contribute()` runs at boot in every run, headless ones included, and
may not import a widget module (`test_module_contribution_laziness.py`). Each
contribution used to meet that with function-local imports inside its
factories, a `PLC0415` hit per factory that `test_ruff_debt_only_shrinks.py`
ratchets and every new screen would have grown (PR #333 review). `Deferred` is
the one place that defers: it holds `"package.module:attribute"` and imports
the module the first time the factory is called — the standard library's
`importlib.import_module`, in the shape of Django's `import_string` and the
`module:attribute` of entry points.

**The cost and what pays it.** A string escapes mypy and the import guards, so
`tests/unit/architecture/test_deferred_targets_resolve.py` resolves every
target the real modules contribute and holds each inside its own module.

Capability: Name a widget or factory by import path so boot imports no widget module
    Also: lazy import, deferred import, late import, contribution factory, PLC0415
    Use: Deferred
    User: src/modules/trading/module.py
    Status: stable
"""

from __future__ import annotations

from importlib import import_module
from typing import cast


class Deferred[R]:
    """@brief `"package.module:attribute"`, imported and called on each call.

    Annotate the variable with the result type (`Deferred[BaseView]`); the
    call returns what the attribute returns, which the guard above checks
    exists and is callable.
    """

    __slots__ = ("_leading", "target")

    def __init__(self, target: str, *leading: object) -> None:
        """@param leading Arguments every call passes first (`bind`).
        @raise ValueError `target` is not `package.module:attribute`."""
        module, separator, attribute = target.partition(":")
        if not (module and separator and attribute):
            raise ValueError(
                f"a deferred target is 'package.module:attribute', not {target!r}"
            )
        self.target = target
        self._leading = leading

    def bind(self, *leading: object) -> Deferred[R]:
        """The same target with `leading` passed first on every call: a factory that needs a
        value known at contribution time (the container) stays a `Deferred`, so the guard that
        resolves every target still sees it (`BOT-148`)."""
        return Deferred(self.target, *self._leading, *leading)

    @property
    def module(self) -> str:
        return self.target.partition(":")[0]

    def resolve(self) -> object:
        """Imports the module and returns the attribute, without calling it."""
        module, _, attribute = self.target.partition(":")
        return getattr(import_module(module), attribute)

    def __call__(self, *args: object) -> R:
        factory = self.resolve()
        if not callable(factory):
            raise TypeError(f"{self.target} is not callable")
        return cast("R", factory(*self._leading, *args))

    def __repr__(self) -> str:
        return f"Deferred({self.target!r})"
