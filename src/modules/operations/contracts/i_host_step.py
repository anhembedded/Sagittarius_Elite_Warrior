"""One thing the host does once, between the app's boot and the first health line (`EPIC-038D`).

The host only sequences. What there is to do at start - say which bots are
RECOVERING, warn that no alert channel exists, start the planned bots - is a
list of steps the entry point hands it, in order; the host runs each one, logs
its name, and stops at the first that raises. A new start-up duty is one class
and one entry in that list; `RunHost` does not change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IHostStep(ABC):
    #: The word the log uses for this step.
    name: str

    @abstractmethod
    def run(self) -> None:
        """Do the step. A raised exception fails the host (exit 1)."""
