"""The pinned timeframes as actions, for a chart's toolbar (`EPIC-033G`).

Reads only `TimeframeSelection.pinned_rows` and `current_code`: one checkable
`QAction` per pinned code, all in one exclusive `QActionGroup`, so the current
timeframe is simply the checked action and the platform draws it; plus a
"More timeframes…" action that asks its host to open the full picker. Opening
is the host's decision, because the pinned set the picker writes is state
these actions must also reflect, so one owner holds both.

Actions rather than buttons (`ui-presentation-rule.md` §6: a toolbar holds
actions, and no checkable push button): a `QToolBar` lays them out with the
style's metrics and moves the ones that do not fit into its extension menu,
where the old row of pills clipped at 1366 px.

`EPIC-025` PR 4.3k made the row checkable `QPushButton`s (it had been
`TimeframeToolbar.qml`); `EPIC-033G` makes it actions.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QActionGroup

from .selection import TimeframeSelection

_MORE_TEXT = "More timeframes…"


class TimeframeActions(QObject):
    """
    @brief One checkable action per pinned timeframe, and one for the rest.

    @details Rebuilt whenever the selection changes, because the *membership*
    changes: pinning adds an action and unpinning removes one. `rebuilt`
    tells the toolbar to re-place them.
    """

    #: The set of timeframe actions changed; `timeframe_actions()` is current.
    rebuilt = Signal()
    #: The host should open the full picker.
    more_requested = Signal()

    def __init__(
        self, selection: TimeframeSelection, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._selection = selection
        self._group = QActionGroup(self)
        self._group.setExclusive(True)
        self._actions: dict[str, QAction] = {}
        self.more_action = QAction(_MORE_TEXT, self)
        self.more_action.setObjectName("actTimeframeMore")
        self.more_action.triggered.connect(self.more_requested)
        selection.stateChanged.connect(self._rebuild)
        self._rebuild()

    def timeframe_actions(self) -> list[QAction]:
        """The pinned timeframes' actions, in pinned order."""
        return list(self._actions.values())

    def action_for(self, code: str) -> QAction | None:
        """A timeframe's action, or `None` when that code is not pinned."""
        return self._actions.get(code)

    def _rebuild(self) -> None:
        for action in self._actions.values():
            self._group.removeAction(action)
            action.deleteLater()
        self._actions.clear()
        for pinned in self._selection.pinned_rows:
            action = QAction(pinned.code, self)
            action.setObjectName(f"actTimeframe_{pinned.code}")
            action.setCheckable(True)
            # Checked before connecting: seeding the current timeframe must not
            # read as the user having chosen it.
            action.setChecked(pinned.current)
            action.triggered.connect(
                # Default-arg capture: a plain closure would hand every action
                # the loop's last code.
                lambda _checked=False, code=pinned.code: self._selection.choose(code)
            )
            self._group.addAction(action)
            self._actions[pinned.code] = action
        self.rebuilt.emit()
