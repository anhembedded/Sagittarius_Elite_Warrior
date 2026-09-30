"""`EPIC-028F` — the exchange refused a leverage or margin-mode change."""

from __future__ import annotations


class AccountControlRejectedError(RuntimeError):
    """The exchange answered and said no (a leverage above the symbol's
    bracket, a margin-mode change with open orders). Carries Binance's own
    error code and message, so the refusal can be shown as the exchange gave
    it."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
