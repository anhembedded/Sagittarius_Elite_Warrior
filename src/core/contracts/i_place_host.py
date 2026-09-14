"""What a surface offers the widgets contributed to it (HLD §4.6).

Implemented by the shell's surface host; `support/ui_kit` also implements it
during the strangler period so a legacy page can host contributions before its
surface exists. A module never holds a reference to the host: the host calls the
module's factory, not the other way round.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.place import Place

if TYPE_CHECKING:  # core/ is Qt-free at runtime; the guard ignores TYPE_CHECKING
    from PySide6.QtWidgets import QWidget


class IPlaceHost(ABC):
    """A surface that can show a widget in one of its places."""

    @property
    @abstractmethod
    def surface_id(self) -> str:
        """The id contributions name — `"trading"`, `"dev_board"`, …"""

    @abstractmethod
    def accepts(self) -> frozenset[Place]:
        """The places this host can actually render."""

    @abstractmethod
    def place_widget(
        self, place: Place, widget: QWidget, *, title: str | None = None
    ) -> None:
        """Show `widget` in `place`. Called on the main thread only."""
