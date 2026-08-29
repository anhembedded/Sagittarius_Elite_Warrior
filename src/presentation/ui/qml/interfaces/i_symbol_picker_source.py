"""Application-neutral data contract for the standalone symbol picker."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence


class ISymbolPickerSource(ABC):
    """Source contract consumed by :class:`SymbolPickerVM`.

    The picker deliberately knows nothing about a screen ViewModel, exchange
    client, persistence store, or application container. A host implements
    this narrow contract and decides where symbols, favourites, recents, and
    the current pair come from.
    """

    @abstractmethod
    def get_symbols(self) -> Sequence[str]:
        """Return the currently available trading pairs."""

    @abstractmethod
    def get_favourites(self) -> Sequence[str]:
        """Return pairs marked as favourites."""

    @abstractmethod
    def get_recents(self) -> Sequence[str]:
        """Return pairs recently selected by the user."""

    @abstractmethod
    def get_current(self) -> str:
        """Return the pair currently selected by the host."""

    @abstractmethod
    def set_favourite(self, symbol: str, favourite: bool) -> None:
        """Persist a favourite toggle raised from the picker.

        Symbols and recents stay host-driven with no picker-side write path;
        favourites is the one piece of state the picker itself can originate
        a change for, so it is the one method on this contract that writes
        back rather than only reading.
        """
