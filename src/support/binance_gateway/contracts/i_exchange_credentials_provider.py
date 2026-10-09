"""`EPIC-021B` — resolving a trading venue's API credentials, env-var first."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)


class CredentialsSource(str, Enum):
    """Which source actually won the resolution — for Settings to tell the
    user where their key is coming from and, when `ENV` wins, to lock the
    input field so an edit that would silently be ignored is not offered."""

    ENV = "env"
    FILE = "file"
    #: `EPIC-034E` — the operating system's keyring (a mainnet venue's key, D10).
    KEYRING = "keyring"
    NONE = "none"


@dataclass(frozen=True)
class ResolvedCredentials:
    """@brief The outcome of one `resolve()` call: the credentials (if any)
    and which source produced them, together — so a caller never has to
    make two calls and risk them disagreeing."""

    credentials: ExchangeCredentials | None
    source: CredentialsSource
    #: Why a key that is stored was not handed out, in plain words (`BUG-193`):
    #: the exchange refused it, or it can withdraw. Empty when there is simply no
    #: key, so a reader never calls a refused key "not configured".
    refusal: str = ""
    #: The value of the `ConnectionFailureKind` behind `refusal`, so a status
    #: row names the same cause as the sentence; empty when `refusal` is.
    refusal_kind: str = ""

    def absence(self, market: str) -> str:
        """What a reader says when it got no credentials: the key is missing, or
        it exists and was refused (with the refusal's own words)."""
        if self.refusal:
            return f"the {market} key cannot be used: {self.refusal}"
        return f"no {market} credentials configured"

    def unusable_because(self, market: str, what_is_blocked: str) -> str:
        """`absence` as a sentence of its own, for an error or a log line: why
        `what_is_blocked` cannot go ahead. The one place a reader words a key it
        did not get, so none can call a refused key "not configured"."""
        reason = self.absence(market)
        return f"{reason[0].upper()}{reason[1:]} — cannot {what_is_blocked}."


class IExchangeCredentialsProvider(ABC):
    """@brief Port for resolving one trading venue's API key/secret
    (`EPIC-021B`, closes `BUG-080`'s credentials-never-reach-anything half).

    @details `resolve()` itself takes no venue parameter: which venue's
    credentials a call resolves is fixed at construction, not per call
    (`EPIC-027G` — a concrete provider is bound to exactly one
    `TradingVenue` for its lifetime, so a caller can never accidentally
    pass the wrong venue at the call site).
    """

    @abstractmethod
    def resolve(self) -> ResolvedCredentials:
        """@brief Resolves credentials in priority order: environment
        variable, then the gitignored file fallback, then none.
        @details Never raises on a missing or malformed file source — that
        degrades to `CredentialsSource.NONE`, the same as no credentials
        configured at all.
        """

    @abstractmethod
    def save_to_file(self, api_key: str, api_secret: str) -> None:
        """@brief Persists a key/secret pair to the file-based fallback
        source only.
        @details Never touches the environment, and never writes to a
        git-tracked file. A no-op in effect while an environment variable
        is set — `resolve()` still prefers it — so callers should check
        `resolve().source` first and stop offering the write when it is
        already `ENV` (Settings locks the field for exactly this reason,
        `EPIC-021B` §2.3).
        """

    @abstractmethod
    def remove_stored(self) -> None:
        """@brief Forgets the key/secret pair this venue's durable store holds
        (`BUG-176`); another venue's pair is never touched.
        @details An environment variable is not stored by the app and stays: a
        caller checks `resolve().source` first, as for `save_to_file`. Nothing
        happens when no pair is stored.
        """
