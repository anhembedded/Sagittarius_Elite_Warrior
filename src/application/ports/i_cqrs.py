from typing import Generic, Protocol, TypeVar

TCommand_contra = TypeVar("TCommand_contra", contravariant=True)
TResponse_co = TypeVar("TResponse_co", covariant=True)


class ICommandHandler(Protocol, Generic[TCommand_contra, TResponse_co]):
    """
    @brief Pure Application Layer definition for CQRS Command Handlers.
    @details Replaces the engine's ICommand to maintain zero framework dependencies.
    """

    def execute(self, command: TCommand_contra) -> TResponse_co: ...


TQuery_contra = TypeVar("TQuery_contra", contravariant=True)
TQueryResult_co = TypeVar("TQueryResult_co", covariant=True)


class IQueryHandler(Protocol, Generic[TQuery_contra, TQueryResult_co]):
    """
    @brief Pure Application Layer definition for CQRS Query Handlers.
    """

    def execute(self, query: TQuery_contra) -> TQueryResult_co: ...
