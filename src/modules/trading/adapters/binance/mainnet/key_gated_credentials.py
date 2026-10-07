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

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_permission_gate import (
    IKeyPermissionGate,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)


class KeyGatedCredentials(IExchangeCredentialsProvider):
    def __init__(
        self, stored: IExchangeCredentialsProvider, gate: IKeyPermissionGate
    ) -> None:
        self._stored = stored
        self._gate = gate

    def resolve(self) -> ResolvedCredentials:
        resolved = self._stored.resolve()
        if resolved.credentials is None or self._gate.check() is None:
            return resolved
        return ResolvedCredentials(None, CredentialsSource.NONE)

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        self._stored.save_to_file(api_key, api_secret)

    def remove_stored(self) -> None:
        self._stored.remove_stored()
