"""Writing configuration, as a port (SDD, "Writing configuration").

`IConfigReader` (application layer) deliberately has no `set()`: most of the app
reads configuration and nothing else. The two places that write — the Settings
sections and the developer-mode switch — need exactly these two calls, so they
get a port of their own instead of downcasting to the Engine's `ConfigManager`
(`settings_presenter.py` does that today; the downcast disappears with this).

`set()` changes the in-memory value; `save()` writes the writable file. Two
calls, not one, because a settings section sets several keys and saves once.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IConfigWriter(ABC):
    @abstractmethod
    def set(self, key: str, value: object) -> None:
        """Record a new value for `key`. Not yet on disk."""

    @abstractmethod
    def save(self) -> None:
        """Persist everything `set()` recorded. Raises `OSError` if the write fails."""
