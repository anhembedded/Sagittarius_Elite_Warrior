"""One thing a command file must satisfy before the host reads it (`EPIC-038J`).

The host's rule for believing a file is the operating system's permissions, and the vetted
implementation of that rule already exists for secret files (`EPIC-038E`). `operations` may not
import that package from its adapters, so this is the port the inbox asks; the composition
root supplies an adapter over the secret-file checks.

@par Extension cases
  · a further requirement (a maximum age on the file's own mtime, a required group) - one
    more implementation in the list the inbox is built with.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class IControlFileCheck(ABC):
    @abstractmethod
    def inspect(self, path: Path, descriptor: int) -> str:
        """The reason the file may not be believed, in words about the file (never its
        contents); `""` when it may. `descriptor` is the file already opened by the caller,
        and the check must judge that descriptor, not the path again. Never raises."""
