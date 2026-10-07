"""`BUG-176` — the places a Binance key can belong to, and what each one said of it.

@details A Binance key is valid in exactly one environment, so adding a key means
asking each environment in turn instead of asking the user which it is. The three
are the three places the app can ask: mainnet (`apiRestrictions`, which also says
what the key may do), Spot Testnet and Futures Testnet. A mainnet key may then be
kept for Spot Mainnet, Futures Mainnet or both, by its permissions; a testnet key
for the one testnet venue that accepted it.

`KeyStanding` separates the four answers that mean different things to the person:
the environment does not know the key (`-2008`, `-2014`: the key was made
elsewhere), it knows the key and refuses it here (`-2015`: an IP off its allowlist
or a missing permission), it accepts it, or it did not answer at all.

Plausible extensions, each a local change: a further environment is one member
here, one row in the probe's table and one label.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_permissions import (
    KeyPermissions,
)


class KeyEnvironment(str, Enum):
    MAINNET = "mainnet"
    SPOT_TESTNET = "spot_testnet"
    FUTURES_TESTNET = "futures_testnet"

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS = {
    KeyEnvironment.MAINNET: "Binance mainnet",
    KeyEnvironment.SPOT_TESTNET: "Spot Testnet",
    KeyEnvironment.FUTURES_TESTNET: "Futures Testnet",
}


class KeyStanding(str, Enum):
    ACCEPTED = "accepted"
    #: The environment does not know this key (`-2008` unknown key, `-2014` bad
    #: key format): it was made for another environment, or mistyped.
    UNKNOWN = "unknown"
    #: The environment knows this key and refuses this request (`-2015`): the IP
    #: is not on the key's allowlist, or the key lacks the permission asked for.
    REFUSED = "refused"
    #: No answer about the key: unreachable, under maintenance, a clock or a
    #: signature fault. `EnvironmentVerdict.failure` says which.
    UNREACHABLE = "unreachable"


@dataclass(frozen=True)
class EnvironmentVerdict:
    environment: KeyEnvironment
    standing: KeyStanding
    #: What the key may do; only mainnet answers it, and only when `ACCEPTED`.
    permissions: KeyPermissions | None = None
    #: Why no answer about the key came, when `standing` is `UNREACHABLE`.
    failure: ConnectionFailureKind | None = None
    #: The exchange's own code and message, then the reason and the fixes, as
    #: `describe_failure` words them (one wording for a log line, the Connect step
    #: and this page). Set only when the exchange answered about the key (`UNKNOWN` or
    #: `REFUSED`); empty otherwise, because a transport error's text can hold the
    #: signed URL, and the page words `failure` by its kind instead.
    reason: str = ""
