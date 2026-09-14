"""The container a module sees during `register()` — a spy, not a substitute.

Two rules of the `register()` hook cannot be checked after the fact, because the
container does not remember enough:

1. **`register()` must not `resolve()`.** Resolving during registration builds
   half an object graph in whatever order the module list happens to have, and
   the failure surfaces later as a missing or wrong dependency in a module that
   did nothing wrong.
2. **Two modules must not claim the same abstract type.** Asking the container
   afterwards cannot tell the two apart: `singleton(IKlines, SqliteKlines)` and
   `singleton(IKlines, RestKlines)` both report the same
   `Registration(concrete=None, lifetime="singleton")`, because a class handed to
   `singleton()` becomes a lazy factory whose return type is unknowable until it
   runs. The claim has to be recorded **as it is made**.

So the shell wraps the real container for the duration of one module's
`register()` and records every claim. This is the "spying container" the SDD's
register-versus-boot table names, and it is the only reason those two rules are
rules rather than hopes.

Everything else delegates unchanged, so a module cannot tell the difference —
which is the point: the guard must not alter the behaviour it is guarding.
"""

from __future__ import annotations

from typing import Any

from sagittarius_engine.interfaces.i_container import IContainer, Registration


class ResolveDuringRegisterError(RuntimeError):
    """A module called `resolve()` from `register()`."""


class RegisteringContainer(IContainer):
    """Records what one module claims, and refuses to resolve for it."""

    def __init__(self, inner: IContainer, module_id: str) -> None:
        self._inner = inner
        self._module_id = module_id
        self._claims: list[type] = []

    @property
    def module_id(self) -> str:
        return self._module_id

    def claims(self) -> tuple[type, ...]:
        """Every abstract type this module registered, in the order it did."""
        return tuple(self._claims)

    # -- IContainer --------------------------------------------------------

    def bind(self, abstract: type[Any], concrete: type[Any]) -> None:
        self._claims.append(abstract)
        self._inner.bind(abstract, concrete)

    def singleton(self, abstract: type[Any], instance_or_factory: Any) -> None:
        self._claims.append(abstract)
        self._inner.singleton(abstract, instance_or_factory)

    def scoped(self, abstract: type[Any], concrete: type[Any]) -> None:
        self._claims.append(abstract)
        self._inner.scoped(abstract, concrete)

    def resolve(self, abstract: type[Any]) -> Any:
        raise ResolveDuringRegisterError(
            f"{self._module_id!r} called resolve({_name(abstract)}) from register(). "
            f"register() may only bind and declare singletons; anything that needs a "
            f"built object graph belongs in boot(), which runs after every module has "
            f"registered."
        )

    def create_scope(self) -> Any:
        raise ResolveDuringRegisterError(
            f"{self._module_id!r} opened a scope from register(); scopes belong to boot()."
        )

    def registrations(self) -> dict[type, Registration]:
        return dict(self._inner.registrations())

    def open_scope_count(self) -> int:
        return self._inner.open_scope_count()


def _name(abstract: type) -> str:
    return getattr(abstract, "__name__", repr(abstract))
