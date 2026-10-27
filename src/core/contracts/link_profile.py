"""`EPIC-047D` — a connection profile: where the host is and how to reach it, never a secret.

A profile names a host, a port, an account (`sew`), a protocol and a **reference** to a key: the path
of a key file, or the SSH agent. It holds no password, no passphrase and no key (charter AC9, SSH
record D4): `problem_of` refuses a key file field that holds key material, so a pasted key never
reaches `ui_state.json`. The protocol is an enum with one member today; a Unix socket, a VPN or a TLS
endpoint is another member and another `ILinkTransport` (P7), not a change to the profile's readers.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

PORT_MAX: Final = 65535
NAME_MAX: Final = 40
DEFAULT_USER: Final = "sew"
_KEY_MARKERS: Final = ("PRIVATE KEY", "-----", "ssh-rsa ", "ssh-ed25519 ")


class LinkProtocol(StrEnum):
    SSH = "ssh"


class KeySource(StrEnum):
    KEY_FILE = "key_file"
    AGENT = "agent"


@dataclass(frozen=True, slots=True)
class ReconnectPolicy:
    """How the supervisor tries again after a cut: the first retry at once, then a growing wait.

    `max_attempts` of `None` keeps trying for as long as the error can change."""

    first_delay_s: float = 0.0
    max_delay_s: float = 10.0
    factor: float = 2.0
    max_attempts: int | None = None

    def delays(self) -> Iterator[float]:
        """The wait before each attempt, in order; ends after `max_attempts`."""
        delay, attempt = self.first_delay_s, 0
        while self.max_attempts is None or attempt < self.max_attempts:
            yield min(delay, self.max_delay_s)
            attempt += 1
            delay = max(delay, 0.5) * self.factor

    def problem(self) -> str | None:
        for label, value in (
            ("the first reconnect delay", self.first_delay_s),
            ("the longest reconnect delay", self.max_delay_s),
        ):
            if not math.isfinite(value) or value < 0:
                return f"{label} is a number of seconds, zero or more"
        if not math.isfinite(self.factor) or self.factor < 1:
            return "the reconnect growth factor is at least 1"
        if self.max_attempts is not None and self.max_attempts < 1:
            return "the reconnect attempts are at least 1, or unlimited"
        return None


@dataclass(frozen=True, slots=True)
class LinkProfile:
    name: str
    host: str
    port: int = 22
    user: str = DEFAULT_USER
    protocol: LinkProtocol = LinkProtocol.SSH
    key_source: KeySource = KeySource.AGENT
    #: The path of a key file; empty unless `key_source` is `KEY_FILE`. Never the key itself.
    key_file: str = ""
    #: The path of the `known_hosts` file that pins the host's key; empty is the user's own.
    known_hosts: str = ""
    connect_timeout_s: float = 10.0
    reconnect: ReconnectPolicy = field(default_factory=ReconnectPolicy)


def problem_of(profile: LinkProfile) -> str | None:
    """Why the profile cannot be used, in a sentence, or `None`."""
    name = profile.name.strip()
    if not name or len(name) > NAME_MAX or name != profile.name:
        return f"the name is 1 to {NAME_MAX} characters, with no space at either end"
    if not profile.host or any(c.isspace() for c in profile.host):
        return "the host is a name or an address, with no space"
    if not 1 <= profile.port <= PORT_MAX:
        return f"the port is between 1 and {PORT_MAX}"
    if not profile.user or any(c.isspace() for c in profile.user):
        return "the user is the account's name, with no space"
    if not math.isfinite(profile.connect_timeout_s) or profile.connect_timeout_s <= 0:
        return "the connect timeout is a number of seconds above zero"
    for path in (profile.key_file, profile.known_hosts):
        if _looks_like_a_secret(path):
            return "a key is kept in a file or an agent; the profile holds only a file's path"
    if profile.key_source is KeySource.KEY_FILE and not profile.key_file.strip():
        return "name the key file, or choose the SSH agent"
    if profile.key_source is KeySource.AGENT and profile.key_file:
        return "a profile that uses the agent names no key file"
    return profile.reconnect.problem()


def _looks_like_a_secret(text: str) -> bool:
    return "\n" in text or any(marker in text for marker in _KEY_MARKERS)
