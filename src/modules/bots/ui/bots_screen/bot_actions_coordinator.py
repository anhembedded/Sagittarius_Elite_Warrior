"""`EPIC-029F` — the Bots screen's commands, run off the UI thread.

One action at a time: the presenter begins it on its own tracker, locks the
screen (`ACTION_IN_FLIGHT`) and hands it here; the answer comes back with its
action id, and the presenter drops it if the action is no longer the current
one (`async-ui-action-rule.md` §1). The use cases answer quickly: they check
the lifecycle table and queue the work on the bot's own worker, which does
the exchange calls.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import failure_detail
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


class BotActionsCoordinator(QObject):
    """@brief Dispatches one bots command on the pool."""

    #: The action id, then the result or `None`, then a failure's detail.
    finished = Signal(int, object, str)

    def __init__(
        self, dispatcher: ICommandDispatcher, thread_manager: IThreadManager
    ) -> None:
        super().__init__()
        self._dispatcher = dispatcher
        self._threads = thread_manager

    def send(self, action_id: int, command: object) -> None:
        self._threads.submit(self._dispatch, action_id, command)

    def _dispatch(self, action_id: int, command: object) -> None:
        try:
            result = self._dispatcher.dispatch(type(command), command)
        except Exception as exc:  # noqa: BLE001 - worker boundary: the refusal is shown in words, not lost to a pool thread
            self.finished.emit(action_id, None, failure_detail(exc))
            return
        if not isinstance(result, BotCommandResult):
            self.finished.emit(
                action_id, None, f"unexpected answer {type(result).__name__}"
            )
            return
        self.finished.emit(action_id, result, "")
