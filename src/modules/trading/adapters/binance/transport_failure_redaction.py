"""`BUG-180` / `EPIC-035O` — a transport failure is worded without a credential or a signature.

`requests` words a connection error with the request's whole URL, and a signed
Binance request holds `signature` in its query (a user-data request holds the
`listenKey`, a header-signed one the API key). The URL is in the error's text,
in the urllib3 error it wraps (the first argument of a `requests` error, and
its `__context__`), and so in every log line and traceback printed from either.

`redact_secrets` is the one function that knows what is secret in a text: the
user-data stream's supervisor (`EPIC-035B`) words its failures through it, and
`redact_transport_failure` applies it to a whole exception chain once, where the
failure is born (`RedactingHttpAdapter`), so no caller above needs to remember to.

What stays is what makes the failure diagnosable: its type, the host, the path
and the unsecret query values (`symbol`, `timestamp`). The exception object
itself is kept, so its class (which the retry policy and every
`except RequestException` read) and its traceback are untouched; only the text
inside changes.
"""

from __future__ import annotations

import re

#: Query values and headers that sign or identify a request. An exception text
#: from the transport can carry the whole request URL.
_SECRET_PATTERNS = (
    re.compile(r"(signature=)[^&\s\"']+", re.IGNORECASE),
    re.compile(r"(listenKey=)[^&\s\"']+", re.IGNORECASE),
    re.compile(r"(api[_-]?key=)[^&\s\"']+", re.IGNORECASE),
    re.compile(r"(X-MBX-APIKEY['\"]?\s*[:=]\s*['\"]?)[^\s,'\"}]+", re.IGNORECASE),
)


def redact_secrets(text: str) -> str:
    """`text` with every signature, listen key and API key value replaced."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1<redacted>", text)
    return text


def redact_transport_failure(failure: BaseException) -> None:
    """Redact `failure`'s text and that of every exception it carries: its
    arguments, its cause and its context. In place: the same object goes on
    to be raised."""
    pending: list[BaseException] = [failure]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        current.args = tuple(
            redact_secrets(arg) if isinstance(arg, str) else arg for arg in current.args
        )
        if isinstance(current, OSError):
            pending.extend(_redact_os_error_fields(current))
        pending.extend(arg for arg in current.args if isinstance(arg, BaseException))
        pending.extend(
            link
            for link in (current.__cause__, current.__context__)
            if link is not None
        )


def _redact_os_error_fields(failure: OSError) -> list[BaseException]:
    """An `OSError` built with an errno words itself from `errno`, `strerror`
    and `filename`, not from `args`. Redacts them; returns the exceptions a
    field carries, which are redacted in their turn."""
    carried: list[BaseException] = []
    for field in ("errno", "strerror", "filename"):
        value = getattr(failure, field)
        if isinstance(value, str):
            setattr(failure, field, redact_secrets(value))
        elif isinstance(value, BaseException):
            carried.append(value)
    return carried
