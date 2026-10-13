"""Where a request to stop comes from (`EPIC-038D`).

The `run` host does not know what a signal is: it asks a source to call
`on_signal` whenever the process is told to stop, and counts the calls (the first
starts the drain, the second skips the wait). A POSIX service manager sends
SIGTERM, a terminal sends SIGINT, a Windows console sends Ctrl-C or Ctrl-Break;
each is one adapter, and a test uses a source it can fire by hand.

@par Extension cases
  · another platform's way of being told to stop - one `IShutdownSignalSource`
    and the factory that picks it; `RunHost` does not change;
  · a request to stop that arrives on a socket (`EPIC-038J`, if the owner ever
    asks for control of a running host) - the same port, a source that calls
    `on_signal` when the request arrives.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class IShutdownSignalSource(ABC):
    @abstractmethod
    def install(self, on_signal: Callable[[], None]) -> None:
        """Start calling `on_signal` for every request to stop.

        `on_signal` takes no argument, does little and never raises: a signal
        handler runs between two instructions of whatever the main thread was doing.
        """

    @abstractmethod
    def restore(self) -> None:
        """Give the process's own handling back. Harmless when nothing is installed,
        and harmless twice."""
