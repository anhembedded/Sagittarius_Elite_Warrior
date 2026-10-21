"""`BUG-176` — one venue's row of the Trading page, from its key and its last check.

@details Pure: the row holds a fingerprint and words, never a key. The state's
words depend on the public address the user looked up (`BOT-224`), so the
presenter keeps the last status and builds the row again when that changes.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_key import VenueKey
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.connection_state_words import (
    NO_KEY,
    NOT_CHECKED,
    StateKind,
    state_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.trading_settings_view_model import (
    KeyRow,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)

_SOURCE_WORDS = {
    CredentialsSource.ENV: "environment variable",
    CredentialsSource.FILE: "secrets.local.json",
    CredentialsSource.KEYRING: "OS keyring",
    CredentialsSource.SYSTEMD_CREDENTIAL: "systemd credential",
    CredentialsSource.SECRET_FILE: "secret file",
    CredentialsSource.NONE: "",
}


def build_row(
    key: VenueKey, checked: ExchangeConnectionStatus | None, public_address: str
) -> KeyRow:
    """`checked` is the venue's last connection check, `None` until there is one;
    `public_address` is "" until the user looks it up."""
    has_key = key.fingerprint is not None
    if has_key:
        shown = f"{key.fingerprint} ({_SOURCE_WORDS[key.source]})"
        state, kind = (
            (NOT_CHECKED, StateKind.UNKNOWN)
            if checked is None
            else state_of(checked, public_address)
        )
    else:
        shown = "—"
        state, kind = NO_KEY, StateKind.UNKNOWN
    return KeyRow(
        venue=key.venue,
        title=key.venue.display_name,
        key=shown,
        state=state,
        state_kind=kind,
        has_key=has_key,
        editable=not key.source.is_provisioned_outside_the_app,
    )
