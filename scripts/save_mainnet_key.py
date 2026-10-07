"""EPIC-034 D5, D10 — keep a mainnet API key in the operating system's keyring.

Usage: save_mainnet_key.py spot|futures

Asks for the key and the secret (the secret is not echoed), asks the exchange what
the key may do, and stores it only if it cannot withdraw (D5). The secret goes into
the operating system's keyring and nowhere else (D10), under the venue's own names:
a Spot key is never read for Futures. This script places no order and neither does
anything it calls; it asks one question of the exchange (`apiRestrictions`).

Exit status: 0 stored, 1 the key was refused or could not be checked (nothing
stored), 2 the key is fine but the keyring cannot store it here (set the two
environment variables instead: BINANCE_SPOT_MAINNET_API_KEY and
BINANCE_SPOT_MAINNET_API_SECRET, or the BINANCE_FUTURES_MAINNET_ pair), 3 the
arguments are wrong.

Run from the superproject root with the venv Python:
    PYTHONPATH=. Sagittarius_Elite_Warrior/.venv/bin/python \
        Sagittarius_Elite_Warrior/scripts/save_mainnet_key.py spot
"""

from __future__ import annotations

import sys
from getpass import getpass

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.keyring_secret_store import (
    KeyringSecretStore,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.mainnet_key_enrolment import (
    enrol_key,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    MainnetCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_VENUES = {"spot": TradingVenue.SPOT_MAINNET, "futures": TradingVenue.FUTURES_MAINNET}


def _say(text: str) -> None:
    sys.stdout.write(text + "\n")


def main(argv: list[str]) -> int:
    arguments = argv[1:]
    venue = _VENUES.get(arguments[0]) if len(arguments) == 1 else None
    if venue is None:
        _say("Usage: save_mainnet_key.py spot|futures")
        return 3
    api_key = getpass(f"{venue.display_name} API key: ").strip()
    api_secret = getpass(f"{venue.display_name} API secret: ").strip()
    if not api_key or not api_secret:
        _say("Nothing stored: a key and a secret are both needed.")
        return 1
    try:
        refused = enrol_key(
            venue,
            ExchangeCredentials(api_key, api_secret),
            MainnetCredentialsProvider(KeyringSecretStore(), venue),
        )
    except SecretStoreUnavailableError as exc:
        _say(f"The key is valid but was not stored: {exc}")
        return 2
    if refused is not None:
        _say(f"Nothing stored: {refused.kind.name} {refused.detail}".rstrip())
        return 1
    _say(
        f"The key was checked and stored in the operating system's keyring ({venue.display_name})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
