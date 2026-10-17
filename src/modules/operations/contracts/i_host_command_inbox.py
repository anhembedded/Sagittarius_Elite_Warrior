"""Where the host finds the commands written for it (`EPIC-038J`).

The inbox is the door: it decides, from the operating system's permissions alone, whether a
file may be believed, and hands the host either its text or the reason it was turned away.
Nothing here parses a command; a file that passes the door is still checked by the host.

@par Extension cases
  · a command source that is not a directory (a chat channel) - it produces the same
    `InboxEntry` values, with `problem` set when its sender is not allowed;
  · a stricter door (a maximum age on the file's own mtime) - one more check in the adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InboxEntry:
    """One file. `text` is set when the file may be believed; `problem` when it may not."""

    name: str
    text: str = ""
    problem: str = ""

    @property
    def authorised(self) -> bool:
        return not self.problem


class IHostCommandInbox(ABC):
    @abstractmethod
    def collect(self) -> Iterator[InboxEntry]:
        """The waiting commands, oldest first, **one at a time**: a file is claimed (taken out
        of the sender's reach) only when the caller asks for it, so a sender that withdraws a
        file the host has not yet taken succeeds, and one that withdraws a file the host has
        taken fails - never the reverse. A directory that is absent, or not safe to read from,
        yields nothing: no control."""

    @abstractmethod
    def discard(self, entry: InboxEntry) -> None:
        """Remove the file so it is neither run nor judged again. A file that cannot be
        removed is remembered and not offered again by this inbox."""
