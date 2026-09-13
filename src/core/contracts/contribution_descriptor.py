"""One shape for every contributed widget (SDD, answers open question O1).

A module does not build UI and does not know where its widget ends up. It hands
the shell a **descriptor**: who is contributing, to which surface, in what
place, roughly how big, and a function that will build the widget later. The
shell validates the descriptor immediately and calls the factory only when the
surface is first shown.

`factory` is the single Qt-typed field, and it is typed under `TYPE_CHECKING`
only, so `core/` imports no toolkit at runtime (`test_module_domain_is_qt_free`).
The function it points at lives in the module's `ui/` package and imports the
widget module **inside its body** — that is what keeps boot from loading every
screen's dependency tree (`abstract_screen_module.py`'s laziness, kept).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.size_hint import SizeHint

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget
    from sagittarius_engine.interfaces.i_container import IContainer

#: The `contributor_id` the shell uses for the surfaces and panels it owns.
SHELL_CONTRIBUTOR_ID = "shell"


@dataclass(frozen=True, slots=True)
class ContributionDescriptor:
    """A widget a module offers to one place on one surface."""

    #: A module id, or `"shell"` for the shell's own contributions — nothing else.
    #: A support package never contributes: the module that wants the widget
    #: contributes it under its own id, so this field keeps one meaning.
    contributor_id: str
    #: The surface it belongs to, e.g. `"trading"`. Unknown ids raise.
    surface_id: str
    place: Place
    #: Sort key within `(surface_id, place)`. **Not** a uniqueness key: two
    #: independently written modules may both pick 10 and still render in a
    #: stable order, rather than refusing to boot.
    order: int
    size_hint: SizeHint
    #: Builds the widget. Never called at contribute time.
    factory: Callable[[IContainer], QWidget]
    #: Shown by RAIL, SETTINGS_SECTION, MODAL and DEV_PROBE; ignored elsewhere.
    title: str | None = None

    def identity(self) -> tuple[str, Place, str, str]:
        """What may appear only once: this widget, in this place, from this
        contributor. Two different factories from one module in one place are
        two panels and are allowed."""
        return (
            self.surface_id,
            self.place,
            self.contributor_id,
            _factory_name(self.factory),
        )


def _factory_name(factory: Callable[..., object]) -> str:
    return getattr(factory, "__qualname__", repr(factory))
