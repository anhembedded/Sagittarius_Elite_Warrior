"""`IWebhookTransport` — one HTTPS POST of a JSON body to a webhook (`EPIC-036G`).

The network boundary of a webhook channel. The channel decides what to send and
what an answer means; the transport only carries the body and hands back what
the server said, so a test drives a channel through every answer with
`FakeWebhookTransport` and never opens a socket (`ci-rule.md` §2).

**A server's answer is a value, whatever its status.** A 404 or a 429 comes
back as a `WebhookResponse`; only "no answer at all" (a timeout, a refused
connection, a name that does not resolve) raises `WebhookUnreachableError`.

**No URL in an error.** The URL of a webhook *is* its secret: whoever holds it
can post to the owner's channel. `WebhookUnreachableError`'s message names the
kind of failure and never the URL, its host's path or the response body.

@par Extension cases
  · Discord (`EPIC-036G`) — the first user;
  · Telegram's `sendMessage`, a dead man's switch ping (`EPIC-036C`, `EPIC-036E`)
    — the same port; a channel that needs a form body or a GET adds a method
    here when it arrives, not before.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue

#: The statuses that mean the server took the message: 2xx.
_ACCEPTED = range(200, 300)


@dataclass(frozen=True, slots=True)
class WebhookResponse:
    """What the server answered: its status, its headers (names in lower case)
    and the start of its body."""

    status: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""

    def __post_init__(self) -> None:
        lowered = {name.lower(): value for name, value in self.headers.items()}
        object.__setattr__(self, "headers", MappingProxyType(lowered))

    @property
    def accepted(self) -> bool:
        return self.status in _ACCEPTED


class WebhookUnreachableError(Exception):
    """The server gave no answer. The message names the kind of failure
    ("timed out", "connection refused"), never the URL."""


class IWebhookTransport(ABC):
    @abstractmethod
    def post_json(self, url: str, body: Mapping[str, JsonValue]) -> WebhookResponse:
        """POST `body` as JSON to `url` once; the server's answer, whatever its status.

        @raise WebhookUnreachableError No answer arrived.
        """
