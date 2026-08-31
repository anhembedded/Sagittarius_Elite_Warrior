"""`EPIC-018F` — explicit contract for `InteractiveShell.default()`'s
handler dispatch table, replacing duck-typing (`self.handlers` held plain
classes with no declared shape; `handler.handle(...)` was "call it and
hope") with a named type per `architecture-rule.md` §2.1."""

from abc import ABC, abstractmethod

from sagittarius_engine import App


class ICliCommandHandler(ABC):
    """One interactive-shell command (`sync`, `stream`, ...)."""

    @staticmethod
    @abstractmethod
    def handle(arg_str: str, app: App) -> None: ...
