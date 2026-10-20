"""`BOT-200` — what checking a key found: the venues it is for, or why it is for none.

@details The question `EnrolKeyCommand` asks before it keeps anything, answered
without keeping it: which environment accepts the key and which venues its
permissions allow. A value, not an exception: a key that works nowhere or one that
can withdraw is an ordinary answer. The verdicts of every environment asked are
always carried, so the report can say why for each.
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


class KeyCheckRefusal(str, Enum):
    #: A key or a secret was left empty. Nothing was asked of the exchange.
    INCOMPLETE = "incomplete"
    #: The key or the secret holds a character a Binance key never has: anything but
    #: printable ASCII with no space. Nothing was asked of the exchange.
    NOT_A_KEY = "not_a_key"
    #: No environment accepted the key; the verdicts say why for each.
    NOT_ACCEPTED = "not_accepted"
    #: Mainnet accepted the key and it can withdraw funds (`EPIC-034` D5).
    WITHDRAWAL_ENABLED = "withdrawal_enabled"
    #: Mainnet accepted the key, but it may trade neither Spot nor Futures.
    NO_TRADING_PERMISSION = "no_trading_permission"


@dataclass(frozen=True)
class KeyCheck:
    #: The venues the key is for. Empty when `refusal` is set. A testnet key is for
    #: one venue; a mainnet key for Spot, Futures or both, by its permissions.
    venues: tuple[TradingVenue, ...]
    verdicts: tuple[EnvironmentVerdict, ...] = ()
    refusal: KeyCheckRefusal | None = None
