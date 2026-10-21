"""What Discord's answer to a webhook message means for the worker (`EPIC-036G`).

| Discord answered | `DeliveryResult` | The worker then |
| :--- | :--- | :--- |
| 2xx | `sent` | marks the delivery SENT |
| 429 | `retry_later(wait)` | pauses the channel at least `wait`, uses no attempt |
| 400, 401, 403, 404 (any other 4xx) | `refused` | fails the delivery, raises `CHANNEL_FAILING` once |
| 5xx, or no answer | `failed` | backs off and tries again, bounded |

**The wait is Discord's.** It is read from the body's `retry_after` (seconds,
fractional), else the `Retry-After` header; a 429 is never answered earlier
(research 036 §1: retrying a 429 early counts as an invalid request, and too
many get the IP banned, which loses every alert). Only when Discord names no
wait at all is `DEFAULT_RETRY_AFTER` used.

A `reason` names the status, never the URL or the response body.
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

#: The wait when a 429 names none (neither body nor header): longer than any
#: per-webhook bucket Discord documents, short against the 24 h expiry.
DEFAULT_RETRY_AFTER = timedelta(seconds=5)

_CLIENT_ERRORS = range(400, 500)


def result_of(response: WebhookResponse) -> DeliveryResult:
    """The worker's view of one answer."""
    if response.accepted:
        return DeliveryResult.sent()
    if response.status == TOO_MANY_REQUESTS:
        return DeliveryResult.retry_later(
            _wait_named_in(response), "Discord rate limited the webhook (429)"
        )
    if response.status in _CLIENT_ERRORS:
        return DeliveryResult.refused(
            f"Discord refused the webhook message ({response.status})"
        )
    return DeliveryResult.failed(f"Discord answered {response.status}")


def _wait_named_in(response: WebhookResponse) -> timedelta:
    seconds = _seconds_in_body(response.body)
    if seconds is None:
        seconds = _seconds(response.headers.get("retry-after", ""))
    wait = wait_of(seconds)
    return DEFAULT_RETRY_AFTER if wait is None else wait


def _seconds_in_body(body: bytes) -> float | None:
    try:
        parsed = json.loads(body)
    except ValueError:  # not JSON (empty, HTML from a proxy): fall back to the header
        return None
    if not isinstance(parsed, dict):
        return None
    value = parsed.get("retry_after")
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return seconds_of(value)


def _seconds(text: str) -> float | None:
    try:
        return seconds_of(float(text))
    except ValueError:  # absent or an HTTP date: Discord sends seconds
        return None
