"""`EPIC-034` D5 — the credentials a mainnet venue's adapters resolve, after the
key gate.

@details Every read and every order of a mainnet venue resolves its key from here
(`VenueAssembly.order_credentials`), so a key that can withdraw is refused by the
one thing all of them share and not by one screen's reader: the order path
(`SessionReadiness`, `ExecuteOrder`), the desk's account tabs, the history and
commission readers and the user data stream all see "no key" for it. The venue's
own `credentials_provider` stays the stored key, ungated: it answers "is there a
key" and takes a saved one without a network call (`venue_key_check`, Options).

A key the gate could not judge is refused as well — a permission that cannot be
read is never guessed (`code/errors.md` #7). The gate remembers an accepted key
for a few minutes (`ApiRestrictionsKeyGate`), so this costs one request per key
per interval and not one per call.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_permission_gate import (
    IKeyPermissionGate,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)

#: What a refusal says when the exchange gave no words of its own.
_REFUSAL_WORDS = {
    ConnectionFailureKind.WITHDRAWAL_ENABLED: (
        "the key can withdraw funds, which this app refuses"
    ),
    ConnectionFailureKind.NETWORK: (
        "the exchange could not be asked what the key may do"
    ),
    ConnectionFailureKind.MAINTENANCE: "the exchange is unavailable",
}


def refusal_words(failure: ConnectFailure) -> str:
    """Why the gate refused, for a reader that got no credentials: the
    exchange's own answer when it gave one (`-2015` and what to do about it),
    else the kind in words. Empty for a key that is simply not configured."""
    if failure.kind is ConnectionFailureKind.NOT_CONFIGURED:
        return ""
    return failure.reply or _REFUSAL_WORDS.get(
        failure.kind, f"the exchange refused the key ({failure.kind.value})"
    )


class KeyGatedCredentials(IExchangeCredentialsProvider):
    def __init__(
        self, stored: IExchangeCredentialsProvider, gate: IKeyPermissionGate
    ) -> None:
        self._stored = stored
        self._gate = gate

    def resolve(self) -> ResolvedCredentials:
        resolved = self._stored.resolve()
        if resolved.credentials is None:
            return resolved
        refused = self._gate.check()
        if refused is None:
            return resolved
        return ResolvedCredentials(None, CredentialsSource.NONE, refusal_words(refused))

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        self._stored.save_to_file(api_key, api_secret)

    def remove_stored(self) -> None:
        self._stored.remove_stored()
