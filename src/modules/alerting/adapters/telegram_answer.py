"""What Telegram's answer to `sendMessage` means for the worker (`EPIC-036C1`).

| Telegram answered | `DeliveryResult` | The worker then |
| :--- | :--- | :--- |
| 2xx | `sent` | marks the delivery SENT |
| 429 | `retry_later(wait)` | pauses the channel at least `wait`, uses no attempt |
| 400 "chat not found", 403 (blocked, or never started) | `refused` with guidance | fails the delivery, raises `CHANNEL_FAILING` once |
| 401 (token rejected), 404, any other 4xx | `refused` | the same |
| 5xx, or no answer | `failed` | backs off and tries again, bounded |

**The wait is Telegram's.** It is read from the body's `parameters.retry_after` (whole seconds;
Telegram can ask for hours), else the `Retry-After` header; a 429 is never answered earlier.
Only when it names none is `DEFAULT_RETRY_AFTER` used.

**A reason is plain guidance and never an echo.** "Chat not found" and a bot that was never
started are the two answers an owner meets first; each is turned into what to do ("open the bot on
Telegram and press Start"). A reason names the status, never the URL (it holds the token), the
body or Telegram's own description text.
"""

from __future__ import annotations

import json
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.retry_wait import (
    seconds_of,
    wait_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    WebhookResponse,
)

TOO_MANY_REQUESTS = 429

#: The wait when a 429 names none: short against the 24 h expiry, longer than a flood bucket.
DEFAULT_RETRY_AFTER = timedelta(seconds=5)

_UNAUTHORIZED = 401
_FORBIDDEN = 403
_BAD_REQUEST = 400
_CLIENT_ERRORS = range(400, 500)

_START_THE_BOT = (
    "Open the bot on Telegram and press Start, then check the chat id and try again"
)


def result_of(response: WebhookResponse) -> DeliveryResult:
    """The worker's view of one answer."""
    if response.accepted:
        return DeliveryResult.sent()
    if response.status == TOO_MANY_REQUESTS:
        return DeliveryResult.retry_later(
            _wait_named_in(response), "Telegram rate limited the bot (429)"
        )
    if response.status == _UNAUTHORIZED:
        return DeliveryResult.refused(
            "Telegram rejected the bot token (401): check the token with @BotFather"
        )
    if response.status == _FORBIDDEN:
        return DeliveryResult.refused(
            f"The bot may not write to this chat (403). {_START_THE_BOT}"
        )
    if response.status == _BAD_REQUEST and _says_chat_not_found(response.body):
        return DeliveryResult.refused(
            f"Telegram did not find the chat (400). {_START_THE_BOT}"
        )
    if response.status in _CLIENT_ERRORS:
        return DeliveryResult.refused(
            f"Telegram refused the message ({response.status})"
        )
    return DeliveryResult.failed(f"Telegram answered {response.status}")


def _says_chat_not_found(body: bytes) -> bool:
    parsed = _object_in(body)
    description = parsed.get("description") if parsed else None
    return isinstance(description, str) and "chat not found" in description.lower()


def _wait_named_in(response: WebhookResponse) -> timedelta:
    seconds = _seconds_in_body(response.body)
    if seconds is None:
        seconds = _seconds(response.headers.get("retry-after", ""))
    wait = wait_of(seconds)
    return DEFAULT_RETRY_AFTER if wait is None else wait


def _seconds_in_body(body: bytes) -> float | None:
    parsed = _object_in(body)
    parameters = parsed.get("parameters") if parsed else None
    if not isinstance(parameters, dict):
        return None
    value = parameters.get("retry_after")
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return seconds_of(value)


def _object_in(body: bytes) -> dict[str, object] | None:
    try:
        parsed = json.loads(body)
    except ValueError:  # not JSON (empty, HTML from a proxy)
        return None
    return parsed if isinstance(parsed, dict) else None


def _seconds(text: str) -> float | None:
    try:
        return seconds_of(float(text))
    except ValueError:  # absent or an HTTP date: Telegram sends seconds
        return None
