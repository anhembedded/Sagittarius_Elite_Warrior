"""`EPIC-021B` — resolving Futures Testnet API credentials, env-var first."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_credentials import (
    ExchangeCredentials,
)


class CredentialsSource(str, Enum):
    """Which source actually won the resolution — for Settings to tell the
    user where their key is coming from and, when `ENV` wins, to lock the
    input field so an edit that would silently be ignored is not offered."""

    ENV = "env"
    FILE = "file"
    NONE = "none"


@dataclass(frozen=True)
class ResolvedCredentials:
    """@brief The outcome of one `resolve()` call: the credentials (if any)
    and which source produced them, together — so a caller never has to
    make two calls and risk them disagreeing."""

    credentials: ExchangeCredentials | None
    source: CredentialsSource


class IExchangeCredentialsProvider(ABC):
    """@brief Port for resolving the Futures Testnet API key/secret
    (`EPIC-021B`, closes `BUG-080`'s credentials-never-reach-anything half).

    @details Exactly one venue ever needs credentials today —
    `TradingVenue.FUTURES_TESTNET` is the only non-`DISABLED` member (no
    `MAINNET` member exists, ADR §3) — so this port takes no venue
    parameter. Revisit if that ever changes.
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
