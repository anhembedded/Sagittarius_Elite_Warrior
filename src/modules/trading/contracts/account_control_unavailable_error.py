"""`EPIC-028F` — a leverage or margin-mode change, or the position read
before it, has no known outcome."""

from __future__ import annotations


class AccountControlUnavailableError(RuntimeError):
    """No credentials, a network failure, or an answer that could not be read.
    For a change the outcome is unknown: it may have been applied, and the
    message says so when the request was sent. The cause is chained."""
