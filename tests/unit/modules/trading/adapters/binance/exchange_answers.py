"""The exchange's wrong answers, as python-binance raises them, for the
resilience tests: a coded refusal, a rate-limit answer with its headers, an
HTML page, and the transport failures a request can end in."""

from __future__ import annotations

import json
from types import SimpleNamespace

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ReadTimeout

PAGE = "<html><head><title>502 Bad Gateway</title></head></html>"


def refusal(
    code: int, message: str = "refused", *, status: int = 400
) -> BinanceAPIException:
    """The exchange read the request and answered with a code."""
    body = json.dumps({"code": code, "msg": message})
    return BinanceAPIException(SimpleNamespace(text=body, headers={}), status, body)


def rate_limited(
    status: int = 429,
    *,
    code: int = -1003,
    retry_after: str | None = None,
    message: str = "Too many requests.",
) -> BinanceAPIException:
    """HTTP 429 or 418 with python-binance's exception, `Retry-After` optional."""
    body = json.dumps({"code": code, "msg": message})
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    return BinanceAPIException(
        SimpleNamespace(text=body, headers=headers), status, body
    )


def html_page(
    status: int = 502, *, retry_after: str | None = None
) -> BinanceAPIException:
    """A gateway's page (`code=0`), as python-binance wraps it."""
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    return BinanceAPIException(
        SimpleNamespace(text=PAGE, headers=headers), status, PAGE
    )


def timeout() -> ReadTimeout:
    return ReadTimeout("read timed out")


def reset() -> RequestsConnectionError:
    return RequestsConnectionError("connection reset by peer")


def unreadable() -> BinanceRequestException:
    return BinanceRequestException("Invalid JSON error message from Binance: <html>")
