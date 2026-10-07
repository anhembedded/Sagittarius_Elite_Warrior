"""`BUG-176` — what adding a key did: which venues now hold it, or why none does.

@details A value, not an exception: a key that works nowhere, one that can
withdraw and a keyring that is locked are ordinary answers the page words. The
verdicts of every environment asked are always carried, so the page can say why
for each when a key works nowhere (`EnrolmentRefusal.UNKNOWN_EVERYWHERE`).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class EnrolmentRefusal(str, Enum):
    #: A key or a secret was left empty. Nothing was asked of the exchange.
    INCOMPLETE = "incomplete"
    #: The key or the secret holds a character a Binance key never has (anything but
    #: ASCII): it cannot be sent, and would be told as a network failure. Nothing
    #: was asked of the exchange.
    NOT_A_KEY = "not_a_key"
    #: No environment accepted the key; the verdicts say why for each.
    NOT_ACCEPTED = "not_accepted"
    #: Mainnet accepted the key and it can withdraw funds (`EPIC-034` D5).
    WITHDRAWAL_ENABLED = "withdrawal_enabled"
    #: Mainnet accepted the key, but it may trade neither Spot nor Futures.
    NO_TRADING_PERMISSION = "no_trading_permission"
    #: The key was asked to replace one venue's key and belongs to another.
    OTHER_VENUE = "other_venue"
    #: A venue the key is for takes its key from an environment variable, which
    #: the app cannot change.
    FROM_ENVIRONMENT = "from_environment"
    #: The key is fine but the operating system's keyring cannot hold it here.
    KEYRING_UNAVAILABLE = "keyring_unavailable"
    #: The key is fine but `secrets.local.json` cannot be written.
    FILE_NOT_WRITABLE = "file_not_writable"


@dataclass(frozen=True)
class KeyEnrolment:
    #: The venues whose key is now this one. Empty when `refusal` is set, except
    #: that a store that failed part-way names the venues it had reached.
    stored: tuple[TradingVenue, ...]
    verdicts: tuple[EnvironmentVerdict, ...] = ()
    refusal: EnrolmentRefusal | None = None
    #: The venue the key belongs to when `refusal` is `OTHER_VENUE`, or the venue
    #: that reads an environment variable when it is `FROM_ENVIRONMENT`.
    venues: tuple[TradingVenue, ...] = ()


class KeyRemoval(str, Enum):
    REMOVED = "removed"
    #: Nothing was stored for the venue: already as asked.
    NOTHING_STORED = "nothing_stored"
    #: The venue's key is an environment variable, which the app cannot remove.
    FROM_ENVIRONMENT = "from_environment"
    KEYRING_UNAVAILABLE = "keyring_unavailable"
    FILE_NOT_WRITABLE = "file_not_writable"
