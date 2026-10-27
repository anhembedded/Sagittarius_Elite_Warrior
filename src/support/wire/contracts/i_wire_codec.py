"""`EPIC-047H` — port: put a contract value into its wire form and take it back, by the root's wire name.

@details What a module needs of the link's codec (`support/wire/wire_roots.py` → `WireRoots`): the host writes its
market-data and host-reads files in the very form the bridge puts on the wire, so a module encodes and decodes by
name without importing the codec's classes (`architecture-rule.md` §3: a module reaches a support package through its
`contracts/`). The shell registers the one registry of the build (`shell/wire_roots.py` → `link_roots`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class WireCodecError(Exception):
    """A value could not be turned into a wire form or back. The message says where and why."""


class IWireCodec(ABC):
    @abstractmethod
    def encode(
        self, name: str, value: object, *, revision: int | None = None
    ) -> dict[str, object]:
        """`value` as the message of the root `name`.
        @raise WireCodecError The root is unknown or `value` is not of its type."""

    @abstractmethod
    def decode(self, doc: object) -> object:
        """The value a message holds, of the type its `schema` names.
        @raise WireCodecError The message is not one of this build's roots, or does not match its type."""
