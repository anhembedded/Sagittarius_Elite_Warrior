"""A presenter that is one page of Tools → Options (`EPIC-033E`).

Every page tracks its edits the same way: the values it last saved, the values
on screen now, and a page that is dirty while the two differ. OK and Apply call
`apply()`, Cancel calls `revert()`, and the dialog hears every edit through the
listener it hands in once. Those bodies were identical in the Trading and the
Market Data pages, so they live here once, and a page supplies only what is its
own: how to read its values from config, which fields it compares, how it saves,
how it takes back a save that did not reach disk, and which view-model signals
mean "edited".

@par A failed save changes nothing
A page writes its values into the live config before the disk write, because
`ConfigManager.save()` writes what is in memory. When the disk write fails,
`apply()` has the page put its saved values back, so the session never runs
on a value the user was told did not save, and a later Cancel reverts to what
is really saved. The page stays dirty, with its error on its status line.

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
    #: The dialog's listener now connected; Tools → Options builds a new
    #: dialog on every open, so the previous one's is dropped.
    _listener: Callable[[], None] | None = None

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
        else:
            self._undo_unsaved_writes()

    def revert(self) -> None:
        self._reload()

    def set_change_listener(self, listener: Callable[[], None]) -> None:
        for signal in self._change_signals():
            if self._listener is not None:
                signal.disconnect(self._listener)
            signal.connect(listener)
        self._listener = listener

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
    def _undo_unsaved_writes(self) -> None:
        """After a failed `_save()`: puts the saved values back wherever
        `_save()` wrote before it failed, leaving the page's edits on screen."""
        raise NotImplementedError("_undo_unsaved_writes")

    @abstractmethod
    def _change_signals(self) -> tuple[SignalInstance, ...]:
        """The view-model signals that mean the user edited the page."""
        raise NotImplementedError("_change_signals")
