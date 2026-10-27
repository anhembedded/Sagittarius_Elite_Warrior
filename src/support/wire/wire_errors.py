"""`EPIC-047A` — the two ways a value fails to cross the wire, each with the path where it failed."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_wire_codec import (
    WireCodecError,
)


class WireError(WireCodecError):
    """A value could not be turned into a wire form or back. The message says where and why."""


class WireSchemaError(WireError):
    """The *type* has no wire form: a float, a union member without a wire name, an unknown class.

    A programming error found on the sending side or at registration, never a bad message.
    """


class WireDecodeError(WireError):
    """A message does not match the type it claims: an unknown wire name, a missing or extra
    field, a wrong type, a value the type's own rule refuses. Nothing is defaulted."""
