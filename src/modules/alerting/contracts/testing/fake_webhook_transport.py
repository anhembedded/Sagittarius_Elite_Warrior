"""`EPIC-036G` — a scripted `IWebhookTransport` for tests: it records each POST and
answers from a script, so no test reaches the network.

Held to the same contract as the real transport
(`contract_webhook_transport.py`): an answer is a `WebhookResponse`, and only a
scripted `WebhookUnreachableError` is raised. Its extras are plain attributes
(`posts`, `script`, `default`, `posted`, `clock`), not methods.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
    WebhookResponse,
    WebhookUnreachableError,
)

#: Discord's answer to an accepted webhook message.
NO_CONTENT = WebhookResponse(204)


@dataclass(frozen=True, slots=True)
class RecordedPost:
    url: str
    body: Mapping[str, JsonValue]
    #: The time the injected clock read when the POST was made; `None` without one.
    at: datetime | None


class FakeWebhookTransport(IWebhookTransport):
    """Answers `script` in order, then `default`."""

    def __init__(
        self,
        script: Sequence[WebhookResponse | WebhookUnreachableError] = (),
        default: WebhookResponse | WebhookUnreachableError = NO_CONTENT,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.script: list[WebhookResponse | WebhookUnreachableError] = list(script)
        self.default = default
        self.posts: list[RecordedPost] = []
        #: Set after every POST: what a threaded test waits on.
        self.posted = threading.Event()
        #: Read at each POST to stamp it; a test may set it after construction.
        self.clock = clock
        self._lock = threading.Lock()

    def post_json(self, url: str, body: Mapping[str, JsonValue]) -> WebhookResponse:
        with self._lock:
            at = self.clock() if self.clock is not None else None
            self.posts.append(RecordedPost(url, dict(body), at))
            outcome = self.script.pop(0) if self.script else self.default
        self.posted.set()
        if isinstance(outcome, WebhookUnreachableError):
            raise outcome
        return outcome
