"""A yes/no a view model already knows, as the `Signal(bool)` a command
binds its enabled or checked state to (`EPIC-033D`).

A view model announces most state with a bare `Signal()` and a property to
read (`uiModeChanged` + `uiMode`). `ICommandBinder.bind` takes a
`Signal(bool)`. `DerivedState` sits between them: it re-reads `read` each
time `notify` fires and emits the answer, so a screen's "the controls apply
while idle" is written once, beside the binding, instead of as one more
signal on every view model.

Plausible extensions, each a local change: a state derived from two
notifications (call `listen` twice); a negation (`read=lambda: not …`).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal, SignalInstance


class DerivedState(QObject):
    """`changed` carries `read()` each time a notification it listens to fires."""

    changed = Signal(bool)

    def __init__(
        self, notify: SignalInstance, read: Callable[[], bool], parent: QObject
    ) -> None:
        """@param parent Owns this object: the view model `read` looks at."""
        super().__init__(parent)
        self._read = read
        self.listen(notify)

    @property
    def value(self) -> bool:
        return self._read()

    def listen(self, notify: SignalInstance) -> None:
        notify.connect(self.announce)

    def announce(self) -> None:
        """Emits the current answer: on each notification, and once by a
        binding that starts after the state was set (a checked state has no
        initial value of its own in `ICommandBinder.bind`)."""
        self.changed.emit(self._read())
