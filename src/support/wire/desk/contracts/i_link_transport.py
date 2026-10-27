"""`EPIC-047D` — the seam under the desktop's link: one open pipe of text lines to the bridge.

`DeskLink` speaks the protocol of `bridge_session.py` over this and knows nothing of SSH. The one
adapter is `asyncssh_transport.py`; a Unix socket, a VPN or a TLS endpoint is another class behind
this port and another `LinkProtocol` member (P7), and a test double is a few lines.

**Threads.** `open` blocks until the pipe is up and is called from a worker, never the UI thread.
`send_line` and `receive_line` may be called from different threads, one each. An adapter that
needs an event loop runs it on a thread of its own and has no blocking call inside it
(`async-ui-action-rule.md`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    LinkProfile,
)


class ILinkTransport(ABC):
    """One session's worth of text lines; a new instance for each connection attempt."""

    @abstractmethod
    def open(self, profile: LinkProfile) -> None:
        """Connect, authenticate, and start the bridge. The caller closes the transport when this
        raises (`close` is idempotent), so a failed `open` need not clean up after itself.

        @raise LinkError the typed reason it could not (`link_errors.py`)."""

    @abstractmethod
    def send_line(self, line: str) -> None:
        """Send one message, the newline added.

        @raise LinkLostError the pipe is closed."""

    @abstractmethod
    def receive_line(self, timeout_s: float) -> str | None:
        """The next line without its newline, or `None` when none came within `timeout_s`.

        @raise LinkLostError the other end is gone (end of file, a reset)."""

    @abstractmethod
    def close(self) -> None:
        """End the session and release everything; idempotent, never raises."""
