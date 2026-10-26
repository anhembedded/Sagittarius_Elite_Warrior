"""`EPIC-047A` — the version handshake: same build, or a refusal in words that names what differs.

The bridge's first line is its `Hello`; the desktop answers with its own. Any difference ends the
session before a single read (decision D6: there is no read-only mode across versions in v1). The
bridge sends `Refusal.to_wire()` and exits; the desktop shows `Refusal.words`.

A `Hello` carries one digest per root, not one digest in all, so the refusal can name *which* wire
form changed instead of saying only "different" (`DERISK.md` §6.4). The digests read wire names and
shapes (`wire_schema.py`), never Python paths, so moving a class refuses nobody.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.wire_name import is_wire_name
from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import WireDecodeError
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots

PROTOCOL = "sew.link/1"
_HELLO_KEYS = {"protocol", "app_version", "roots"}
#: What a peer may put in text the desktop will show: no control characters, bounded.
_PRINTABLE = re.compile(r"[ -~]{1,64}")
_DIGEST = re.compile(r"[0-9a-f]{16}")


@dataclass(frozen=True, slots=True)
class Hello:
    """What one end of the link says about itself."""

    protocol: str
    app_version: str
    root_hashes: Mapping[str, str]

    def to_wire(self) -> dict[str, object]:
        return {
            "protocol": self.protocol,
            "app_version": self.app_version,
            "roots": dict(self.root_hashes),
        }

    @staticmethod
    def from_wire(doc: object) -> Hello:
        if type(doc) is not dict:
            raise WireDecodeError("a hello is an object")
        if doc.keys() != _HELLO_KEYS:
            raise WireDecodeError(
                f"a hello has exactly {', '.join(sorted(_HELLO_KEYS))}"
            )
        protocol, version, roots = doc["protocol"], doc["app_version"], doc["roots"]
        if type(protocol) is not str or not _PRINTABLE.fullmatch(protocol):
            raise WireDecodeError(
                "a hello's protocol is printable ASCII, up to 64 characters"
            )
        if type(version) is not str or not _PRINTABLE.fullmatch(version):
            raise WireDecodeError(
                "a hello's app_version is printable ASCII, up to 64 characters"
            )
        if type(roots) is not dict:
            raise WireDecodeError("a hello's roots map a wire name to a digest")
        for name, digest in roots.items():
            if not is_wire_name(name):
                raise WireDecodeError(
                    f"a hello's root {str(name)[:40]!r} is not a wire name"
                )
            if type(digest) is not str or not _DIGEST.fullmatch(digest):
                raise WireDecodeError(
                    f"a hello's digest for {name} is 16 lowercase hex digits"
                )
        return Hello(protocol, version, dict(roots))


@dataclass(frozen=True, slots=True)
class Refusal:
    """Why the link will not open: what differs, and the sentence the desktop shows."""

    differs: tuple[str, ...]
    words: str

    def to_wire(self) -> dict[str, object]:
        return {
            "type": "refused",
            "reason": "incompatible",
            "differs": list(self.differs),
            "words": self.words,
        }


def hello_of(roots: WireRoots, app_version: str) -> Hello:
    """This build's hello."""
    return Hello(PROTOCOL, app_version, roots.root_hashes())


def judge(host: Hello, desk: Hello) -> Refusal | None:
    """`None` when the two builds speak the same wire; otherwise the refusal."""
    differs: list[str] = []
    notes: list[str] = []
    if host.protocol != desk.protocol:
        differs.append("protocol")
        notes.append(f"the host speaks {host.protocol}, this desktop {desk.protocol}")
    if host.app_version != desk.app_version:
        differs.append("app_version")
    for name in sorted(host.root_hashes.keys() | desk.root_hashes.keys()):
        theirs, ours = host.root_hashes.get(name), desk.root_hashes.get(name)
        if theirs == ours:
            continue
        differs.append(f"wire:{name}")
        notes.append(_wire_note(name, theirs, ours))
    if not differs:
        return None
    words = (
        f"the VPS host runs build {host.app_version}, this desktop runs {desk.app_version}: "
        "run `sudo sew-update`"
    )
    if notes:
        words += f" ({'; '.join(notes)})"
    return Refusal(tuple(differs), words)


def _wire_note(name: str, host_hash: str | None, desk_hash: str | None) -> str:
    if host_hash is None:
        return f"the host lacks {name}"
    if desk_hash is None:
        return f"this desktop lacks {name}"
    return f"{name} differs"
