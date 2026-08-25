"""
@brief `EngineCommandDispatcher` — implements `ICommandDispatcher` on top of
the engine's `IDispatcher`.

@details The second adapter `EPIC-008F`'s acceptance bar required without
listing it (see `application/ports/i_command_dispatcher.py`). Infrastructure is
where naming `IDispatcher` is allowed (`code-rule.md` §5).
"""

from Sagittarius_Elite_Warrior.src.application.ports.i_command_dispatcher import (
    ICommandDispatcher,
)
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher


class EngineCommandDispatcher(ICommandDispatcher):
    """
    @brief Dispatches commands through the engine's dispatcher.
    """

    def __init__(self, dispatcher: IDispatcher) -> None:
        self._dispatcher = dispatcher

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        """@brief Runs the handler registered for `handler_class`."""
        return self._dispatcher.dispatch(handler_class, input_dto)
