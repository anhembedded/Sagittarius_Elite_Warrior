from typing import Protocol, TypeVar, Generic

TCommand = TypeVar("TCommand", contravariant=True)
TResponse = TypeVar("TResponse", covariant=True)

class ICommandHandler(Protocol, Generic[TCommand, TResponse]):
    """
    @brief Pure Application Layer definition for CQRS Command Handlers.
    @details Replaces the engine's ICommand to maintain zero framework dependencies.
    """
    def execute(self, command: TCommand) -> TResponse:
        ...
