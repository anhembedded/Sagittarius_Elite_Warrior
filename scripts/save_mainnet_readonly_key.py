"""EPIC-034E — keep the read-only mainnet API key in the operating system's keyring.

Asks for the key and the secret (the secret is not echoed), reads the account
with them to check them, and stores them only if the read succeeded. A key that
can withdraw is refused and nothing is stored. The key is only ever read with:
this script places no order and neither does anything it calls.

Exit status: 0 stored, 1 the key was refused or could not be read (nothing
stored), 2 the key is fine but the keyring cannot store it here (set the two
environment variables instead: BINANCE_MAINNET_READONLY_API_KEY and
BINANCE_MAINNET_READONLY_API_SECRET).

Run from the superproject root with the venv Python:
    PYTHONPATH=. Sagittarius_Elite_Warrior/.venv/bin/python \
        Sagittarius_Elite_Warrior/scripts/save_mainnet_readonly_key.py
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
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.mainnet_read_session_factory import (
    MainnetReadSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.mainnet_readonly_credentials import (
    MainnetReadOnlyCredentials,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)


def _say(text: str) -> None:
    sys.stdout.write(text + "\n")


def main() -> int:
    api_key = getpass("Mainnet read-only API key: ").strip()
    api_secret = getpass("Mainnet read-only API secret: ").strip()
    if not api_key or not api_secret:
        _say("Nothing stored: a key and a secret are both needed.")
        return 1
    keep = MainnetReadOnlyCredentials(KeyringSecretStore())
    try:
        answer = enrol_key(
            ExchangeCredentials(api_key, api_secret), MainnetReadSessionFactory(), keep
        )
    except SecretStoreUnavailableError as exc:
        _say(f"The key is valid but was not stored: {exc}")
        return 2
    if isinstance(answer, ConnectFailure):
        _say(f"Nothing stored: {answer.kind.name} {answer.detail}".rstrip())
        return 1
    _say("The key was checked and stored in the operating system's keyring.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
