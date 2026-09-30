"""`EPIC-028F` — a leverage or margin-mode change could not reach the
exchange."""

from __future__ import annotations


class AccountControlUnavailableError(RuntimeError):
    """No credentials, or a network failure: the exchange never answered, so
    nothing is known to have changed. The cause is chained."""
