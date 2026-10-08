"""`BUG-180` / `EPIC-035O` — the transport every python-binance session sends through.

`requests.Session` hands each request to an adapter, and a connection that
fails raises out of the adapter. Mounted on a client's session by `new_client`
(the one place a trading client is built), this adapter takes the query string
out of the failure before anything above can log it: the retry policy, the
gateway's `logger.exception`, the connection check and the account readers all
read an exception that never had it.
"""

from __future__ import annotations

from requests import PreparedRequest, Response
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.transport_failure_redaction import (
    redact_transport_failure,
)


class RedactingHttpAdapter(HTTPAdapter):
    """An `HTTPAdapter` whose failures carry no query string."""

    def send(
        self, request: PreparedRequest, *args: object, **kwargs: object
    ) -> Response:
        try:
            return super().send(request, *args, **kwargs)  # type: ignore[arg-type]
        except RequestException as failure:
            redact_transport_failure(failure)
            raise
