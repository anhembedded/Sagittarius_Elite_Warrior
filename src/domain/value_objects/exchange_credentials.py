"""`EPIC-021B` — API key/secret pair for signing exchange requests."""

from __future__ import annotations

from dataclasses import dataclass

#: `__repr__`/`__str__` never show the real secret, and the key is shown only
#: partially masked — enough for a user to recognize *which* key is loaded
#: (e.g. to tell two testnet accounts apart) without the full value ever
#: reaching a log line.
_MASKED = "***"
_VISIBLE_PREFIX = 4
_VISIBLE_SUFFIX = 4


def _partially_mask(value: str) -> str:
    if len(value) <= _VISIBLE_PREFIX + _VISIBLE_SUFFIX:
        return _MASKED
    return f"{value[:_VISIBLE_PREFIX]}…{value[-_VISIBLE_SUFFIX:]}"


@dataclass(frozen=True)
class ExchangeCredentials:
    """@brief An API key/secret pair, exactly as `IExchangeCredentialsProvider`
    resolves it.

    @details `__repr__`/`__str__` are overridden, not just "remember not to
    log this one" — an unhandled exception's traceback, `logger.debug(f"{obj}")`,
    and a pytest assertion diff on a failing test all call `repr()`
    automatically. A secret leaks into a log not because someone chose to log
    it, but because a dataclass's default repr prints every field verbatim
    inside a traceback nobody anticipated.
    """

    api_key: str
    api_secret: str

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"api_key={_partially_mask(self.api_key)!r}, "
            f"api_secret={_MASKED!r})"
        )

    def __str__(self) -> str:
        return repr(self)
