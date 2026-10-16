"""`IWebhookTransport` over the standard library's `urllib` (`EPIC-036G`).

No new dependency (N1, design 036 §2): a webhook message is one POST, as the
Telegram channel already sends with `urllib`. The process's proxy settings
(`HTTPS_PROXY`) apply, as they do to every `urllib` request.

The URL is the secret: it never reaches an exception message or a log line
here. `urllib`'s own errors are reduced to their kind before they leave
(`HTTPError` carries the URL in its attributes, a `URLError`'s reason can quote
the host), and every cause is dropped (`from None`): a chained `urllib` error
would print the URL in a traceback.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
    WebhookResponse,
    WebhookUnreachableError,
)

#: How long one POST may take before it counts as no answer. A webhook answers
#: in well under a second; ten bounds how long a lane can hang inside a dead
#: connection, and the worker's back-off tries again after it.
REQUEST_TIMEOUT_S = 10.0

#: How much of a response body is read: enough for a rate-limit or error JSON.
MAX_BODY_BYTES = 64 * 1024

#: Discord refuses Python's default `User-Agent` (Cloudflare error 1010), so the
#: app names itself.
USER_AGENT = "SagittariusEliteWarrior-alerting/1"


class UrllibWebhookTransport(IWebhookTransport):
    def __init__(self, timeout_s: float = REQUEST_TIMEOUT_S) -> None:
        self._timeout_s = timeout_s

    def post_json(self, url: str, body: Mapping[str, JsonValue]) -> WebhookResponse:
        request = urllib.request.Request(  # noqa: S310 - the scheme is checked by the channel, which only passes https webhook URLs
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as reply:  # noqa: S310 - see above
                return WebhookResponse(
                    reply.status,
                    dict(reply.headers.items()),
                    reply.read(MAX_BODY_BYTES),
                )
        except urllib.error.HTTPError as answered:
            with answered:
                return WebhookResponse(
                    answered.code,
                    dict(answered.headers.items()),
                    answered.read(MAX_BODY_BYTES),
                )
        except TimeoutError:
            raise WebhookUnreachableError("timed out") from None
        except urllib.error.URLError as error:
            raise WebhookUnreachableError(
                f"no answer ({type(error.reason).__name__})"
            ) from None
        except OSError as error:
            raise WebhookUnreachableError(
                f"no answer ({type(error).__name__})"
            ) from None
