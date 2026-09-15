"""What a surface offers the widgets contributed to it (HLD §4.6).

Implemented by the shell's surface host (`shell/workbench_surface.py`);
`support/ui_kit` also implements it during the strangler period so a legacy
page can host contributions before its surface exists. A module never holds a
reference to the host: the host calls the module's factory, not the other way
round.

@par Why `typing.Protocol` and not an ABC — reason (a) of `architecture-rule.md` §2.1
The implementer is a `QMainWindow`, so it is a `QObject` subclass, and
`ABCMeta` has a metaclass conflict with Shiboken's: an ABC here **does not
run**, it is not merely the worse option. `EPIC-025` PR 1.4a found that the
literal way — `class WorkbenchSurface(QMainWindow, IPlaceHost)` raised
`TypeError: metaclass conflict` on import — and reason (b) applies on top,
since a `QMainWindow` subclass already has its own base.

This is the same reason and the same shape as `IStateContributor`
(`EPIC-010C`), whose own docstring records it for `MainWindow`; that file is
the precedent this one follows rather than inventing a second answer
(`onb` §12.5). `@runtime_checkable`, so a test can still `isinstance()` a host
and the name stays greppable — a Protocol drops the inheritance requirement,
not the contract.

Unlike a Protocol under `presentation/`, this one is not left to a test alone:
`shell/` is inside the `mypy` gate (only `src/presentation/` is excluded), so
an implementer that drifts from this declaration fails the gate statically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from Sagittarius_Elite_Warrior.src.core.contracts.place import Place

if TYPE_CHECKING:  # core/ is Qt-free at runtime; the guard ignores TYPE_CHECKING
    from PySide6.QtWidgets import QWidget


@runtime_checkable
class IPlaceHost(Protocol):
    """A surface that can show a widget in one of its places."""

    @property
    def surface_id(self) -> str:
        """The id contributions name — `"trading"`, `"dev_board"`, …"""
        ...

    def accepts(self) -> frozenset[Place]:
        """The places this host can actually render."""
        ...

    def place_widget(
        self, place: Place, widget: QWidget, *, title: str | None = None
    ) -> None:
        """Show `widget` in `place`. Called on the main thread only."""
        ...
