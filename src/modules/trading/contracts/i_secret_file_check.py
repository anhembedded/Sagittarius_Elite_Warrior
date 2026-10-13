"""`EPIC-038E` — one thing a secret file must satisfy before it is read.

@details A file store asks each check in turn and reads the file only when all of
them accept it. A check has one reason to change: the permission rule of one
operating system, or where the file may live. Adding a rule (a maximum age, a
required group) is a class and an entry in the list the store is built with.

A verdict carries **words about the file, never its contents**: the problem is
stated in terms of the path, a mode or an account, and the fix is the command
that repairs it. Both may reach a log line, a pre-flight report and `--json`.

Capability: Decide whether a secret file may be read
    Also: file permission, owner-only, ACL, icacls, chmod, git work tree
    Use: ISecretFileCheck, SecretFileVerdict
    User: src/modules/trading/adapters/binance/mainnet/permission_checked_file_store.py
    Status: stable
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SecretFileVerdict:
    """Accepted when `problem` is empty."""

    #: What is wrong, in plain words: never the file's contents.
    problem: str = ""
    #: The command that makes the file acceptable, naming the file's path.
    fix: str = ""

    @property
    def accepted(self) -> bool:
        return not self.problem


class ISecretFileCheck(ABC):
    @abstractmethod
    def inspect(self, path: Path, descriptor: int) -> SecretFileVerdict:
        """The verdict on `path`, which the caller has already opened as
        `descriptor`. A check about the file itself (owner, mode) asks the
        descriptor, never the path again, so the file it judges is the file that is
        read: the path could be swapped between the check and the read. A check about
        where the file lives uses the path. Never reads the file's contents, never
        raises: a file that cannot be inspected is refused, with the reason."""
