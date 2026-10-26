"""`EPIC-047A` — the name a record has on the remote link, kept with the record.

A union of records travels with a tag, and the version handshake compares names; if the tag
were the Python class path, moving a class to another module would refuse every desktop with
the wire unchanged (`DERISK.md` §6.4). A wire name is explicit instead: `sew.<words>/<n>`,
the same shape `host_command_codec.py` and `health_snapshot.py` give their `schema` field.
Renaming or moving the class changes nothing; changing the name is a version change.

@par Extension cases
  · a new member of a tagged union - one `@wire_name("sew.…/1")` on the new record;
  · a changed wire form that an older build must not read - the new name ends `/2`.
"""

from __future__ import annotations

import re
from collections.abc import Callable

_NAME_SHAPE = re.compile(r"sew\.[a-z0-9]+(?:-[a-z0-9]+)*/[0-9]+")
_ATTRIBUTE = "__wire_name__"


def wire_name[T: type](name: str) -> Callable[[T], T]:
    """Give a record class the name it has on the wire. Apply it above `@dataclass`."""
    if _NAME_SHAPE.fullmatch(name) is None:
        raise ValueError(f"a wire name reads 'sew.some-words/1', not {name!r}")

    def attach(cls: T) -> T:
        setattr(cls, _ATTRIBUTE, name)
        return cls

    return attach


def wire_name_of(cls: type) -> str | None:
    """The class's own wire name, `None` when it has none (a subclass does not inherit it)."""
    name = cls.__dict__.get(_ATTRIBUTE)
    return name if isinstance(name, str) else None
