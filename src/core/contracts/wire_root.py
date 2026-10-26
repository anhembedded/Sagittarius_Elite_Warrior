"""`EPIC-047A` — one type the remote link carries, under the name it has there.

A module declares its roots with this value and the shell hands the whole list to the codec
(`support/wire`), so the codec imports no module and a module imports no codec: the list is
the only place a type becomes carriable, and adding one is one entry in it (P7).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WireRoot:
    """A wire name (`sew.bot-snapshot/1`) and the type hint behind it: a record or a union of records."""

    name: str
    hint: object
