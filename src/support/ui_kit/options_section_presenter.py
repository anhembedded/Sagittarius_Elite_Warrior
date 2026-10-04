"""A presenter that is one page of Tools → Options (`EPIC-033E`).

Every page tracks its edits the same way: the values it last saved, the values
on screen now, and a page that is dirty while the two differ. OK and Apply call
`apply()`, Cancel calls `revert()`, and the dialog hears every edit through the
listener it hands in once. Those bodies were identical in the Trading and the
Market Data pages, so they live here once, and a page supplies only what is its
own: how to read its values from config, which fields it compares, how it saves,
and which view-model signals mean "edited".

@par `@abstractmethod` without `ABC`, the `BaseFeed` pattern
`BasePresenter` is a `QObject`, whose metaclass is Shiboken's, and mixing
`ABCMeta` into it raises a metaclass conflict. So the decorator documents the
contract and the body raises, as `support/ui_kit/table_model.py` does: a page
that forgets a hook breaks on its first call with the hook's name in the error.

Plausible extensions, each a local change: a page that confirms before leaving
it (one hook here, one call in the dialog); a page that saves off the UI thread
(override `apply`).
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from sagittarius_engine.extensions.pyside_mvc import BasePresenter

if TYPE_CHECKING:
    from PySide6.QtCore import SignalInstance
    from sagittarius_engine.interfaces.i_container import IContainer


class OptionsSectionPresenter[TFields](BasePresenter):
    """Satisfies `IOptionsSection` for a page whose state is one value `TFields`."""

    _saved_fields: TFields

    def __init__(self, view: QWidget, container: IContainer, *, title: str) -> None:
        super().__init__(view, container)
        self._title = title

    @property
    def title(self) -> str:
        return self._title

    def widget(self) -> QWidget:
        return self.view

    def is_dirty(self) -> bool:
        return self._current_fields() != self._saved_fields

    def validation_message(self) -> str | None:
        """No objection by default; a page with a rule overrides it."""
        return None

    def apply(self) -> None:
        if self._save():
            self._saved_fields = self._current_fields()

    def revert(self) -> None:
        self._reload()

    def set_change_listener(self, listener: Callable[[], None]) -> None:
        for signal in self._change_signals():
            signal.connect(listener)

    def _reload(self) -> None:
        """Reads the page from config and takes what it shows as saved."""
        self._load_from_config()
        self._saved_fields = self._current_fields()

    @abstractmethod
    def _load_from_config(self) -> None:
        """Puts the saved values on the page."""
        raise NotImplementedError("_load_from_config")

    @abstractmethod
    def _current_fields(self) -> TFields:
        """The values on the page now, comparable with `==`."""
        raise NotImplementedError("_current_fields")

    @abstractmethod
    def _save(self) -> bool:
        """Writes the page; `True` when everything reached disk."""
        raise NotImplementedError("_save")

    @abstractmethod
    def _change_signals(self) -> tuple[SignalInstance, ...]:
        """The view-model signals that mean the user edited the page."""
        raise NotImplementedError("_change_signals")
