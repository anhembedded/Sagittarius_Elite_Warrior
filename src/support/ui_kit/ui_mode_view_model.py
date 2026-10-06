"""A screen ViewModel's FSM mode, and whether its controls are enabled in it.

The Engine's `BaseQmlViewModel` carried the same contract for QML screens, as
`QtCore.Property` declarations. A `QObject` class with a Property is the one
PySide6 6.9–6.11 cannot collect at exit, so the sanity run ended with
`gc: N uncollectable objects at shutdown` (`BUG-152`). No screen here is QML
any more: the readers below are plain Python properties, the two change
signals are the notification, and nothing else of that base was used.

Extension cases, each local: a screen opting into the lock lists its busy
modes in `DISABLED_UI_MODES`; a screen with a second derived switch adds a
property and a signal beside `controlsEnabled` in its own subclass.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

_INITIAL_UI_MODE = "IDLE"


class UiModeViewModel(QObject):
    """@brief The FSM-driven `uiMode` a screen's presenter sets, and the
    `controlsEnabled` switch derived from it."""

    uiModeChanged = Signal()
    controlsEnabledChanged = Signal()

    #: The `uiMode` values that disable this screen's controls; a subclass
    #: opts in (e.g. a run, a cancel, a sync). Empty: always enabled.
    DISABLED_UI_MODES: frozenset[str] = frozenset()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._ui_mode = _INITIAL_UI_MODE
        self._controls_enabled = _INITIAL_UI_MODE not in self.DISABLED_UI_MODES

    @property
    def uiMode(self) -> str:
        return self._ui_mode

    @property
    def controlsEnabled(self) -> bool:
        return self._controls_enabled

    @Slot(str)
    def set_ui_mode(self, mode: str) -> None:
        """Both values change before either signal fires: a directly
        connected slot runs inside `emit()`, and one listening to
        `uiModeChanged` must read the new `controlsEnabled`, not the old.
        `controlsEnabledChanged` fires only when the switch flips."""
        if mode == self._ui_mode:
            return
        self._ui_mode = mode
        enabled = mode not in self.DISABLED_UI_MODES
        flipped = enabled != self._controls_enabled
        self._controls_enabled = enabled

        self.uiModeChanged.emit()
        if flipped:
            self.controlsEnabledChanged.emit()
