"""`EPIC-047E` — the container the VPS Bots tab is built from: the application's, with a few answers of its own.

@details The Bots screen's presenter takes a container and resolves what it needs from it (`EPIC-048C` narrows that). The VPS
tab must be the same presenter class on another backend, so it is handed this: every resolve goes to the application's container
except the few types the tab answers itself (its bus, the link, and the venues it serves on this computer: none). Nothing is
bound in the application's container, so the Bots tab beside it sees none of it.

@par Extension cases
  · another type the tab answers itself - one more `singleton` call where the container is built.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from typing import Any

from sagittarius_engine.interfaces.i_container import IContainer, Registration


class VpsContainer(IContainer):
    def __init__(self, base: IContainer) -> None:
        self._base = base
        self._own: dict[type, object] = {}

    def singleton(self, abstract: type[Any], instance_or_factory: object) -> None:
        """The tab answers `abstract` with this instance (a factory is not accepted: every answer here exists
        before the tab is built)."""
        self._own[abstract] = instance_or_factory

    def resolve(self, abstract: type[Any]) -> object:
        if abstract in self._own:
            return self._own[abstract]
        return self._base.resolve(abstract)

    def registrations(self) -> Mapping[type, Registration]:
        own = {
            abstract: Registration(abstract, None, "singleton", True)
            for abstract in self._own
        }
        return {**self._base.registrations(), **own}

    def bind(self, abstract: type[Any], concrete: type[Any]) -> None:
        self._base.bind(abstract, concrete)

    def scoped(self, abstract: type[Any], concrete: type[Any]) -> None:
        self._base.scoped(abstract, concrete)

    def create_scope(self) -> AbstractContextManager[object]:
        return self._base.create_scope()

    def open_scope_count(self) -> int:
        return self._base.open_scope_count()
