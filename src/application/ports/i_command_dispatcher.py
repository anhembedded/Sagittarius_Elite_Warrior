"""
@brief `ICommandDispatcher` — lets one use case invoke another without
depending on the engine's dispatcher or on the other handler's concrete class.

@details
`BulkSyncMarketDataCommandHandler` dispatches `SyncMarketDataCommand` per
symbol. It depends on a dispatcher rather than on
`SyncMarketDataCommandHandler` directly, and that indirection is the point —
the bulk handler must not own the single-symbol handler's construction or its
dependencies. What it should *not* also have to depend on is the engine's
`IDispatcher`, which is what this port replaces (`EPIC-008F`; see
`i_config_reader.py` for why this port and that one are in the task even
though its numbered requirements omitted both).
"""

from abc import ABC, abstractmethod


class ICommandDispatcher(ABC):
    """
    @brief Dispatches a command to whichever handler is registered for it.
    """

    @abstractmethod
    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        """
        @brief Runs the handler registered for `handler_class` against
        `input_dto` and returns its result.

        @details `handler_class` is the command *type* used as the lookup key,
        not an instance — resolution and construction belong to the adapter,
        which is the only side that knows the container.
        """
        ...
