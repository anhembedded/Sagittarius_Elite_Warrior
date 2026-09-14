"""
@brief CQRS handler ports — `ICommandHandler` and `IQueryHandler`.

@details Application-layer definitions, deliberately not the engine's own
`ICommand`/`IQuery`, so this layer carries zero framework dependencies
(`code-rule.md` §5).

**`ABC`, not `Protocol` (`EPIC-008F`).** Both were `Protocol` before. A
`Protocol` is structural and checked only by the type checker: a handler that
forgets `execute()` still constructs and still runs, failing later at the call
site with an `AttributeError` far from the class that is actually wrong. An
`ABC` refuses to instantiate at all, naming the missing method. Every one of
the 17 handlers already declared the inheritance explicitly even while it was
optional, so this makes the existing contract enforced rather than imposing a
new one.
"""

from abc import ABC, abstractmethod


class ICommandHandler[TCommand, TResponse](ABC):
    """
    @brief Handles exactly one command type and returns its result.

    @details PEP 695 type parameters, which work with `ABC` — the class's own
    `[TCommand, TResponse]` are real, scoped type variables. The module used to
    also declare `TypeVar("TCommand_contra", contravariant=True)` and friends at
    module level; those were dead, shadowed by these same-named PEP 695
    parameters, and were removed in `EPIC-008F`.
    """

    @abstractmethod
    def execute(self, command: TCommand) -> TResponse:
        """@brief Executes the command and returns its result."""
        ...


class IQueryHandler[TQuery, TQueryResult](ABC):
    """
    @brief Answers exactly one query type.
    """

    @abstractmethod
    def execute(self, query: TQuery) -> TQueryResult:
        """@brief Executes the query and returns its result."""
        ...
