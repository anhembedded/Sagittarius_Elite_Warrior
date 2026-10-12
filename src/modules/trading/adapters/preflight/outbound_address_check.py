"""Why the exchange might refuse this machine's key, and the address it saw (`EPIC-038F`, research R6).

Binance answers `-2015` for three different faults in one sentence: the key is
not for this environment (or is mistyped), the key is restricted to addresses
and this machine's is not among them, or the key lacks the permission asked
for. This check turns the bare code into the checklist.

**The address.** The exchange has no "what is my address" request. Binance
names the address in a `-2015` reply (`request ip: ...`), so the check reports
it when a reply carried one and says plainly when none did; it never asks a
third-party service. When the exchange accepted the key from this machine the
restriction is satisfied and the address is not needed. A restriction is per
address, and a dual-stack host may go out over IPv6 while only IPv4 is listed,
so the address's family is reported with it.
"""

from __future__ import annotations

import ipaddress
import re

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckCause,
    CheckFinding,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.unreadable_connection import (
    unreadable_connection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_checks import (
    PerVenueCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)

_REQUEST_IP = re.compile(r"request ip:\s*([0-9a-fA-F:.]+)", re.IGNORECASE)

CHECKLIST = (
    "The exchange gives one error for three causes; check in this order: "
    "(1) the key belongs to this environment (a testnet key does not work on mainnet, "
    "nor the reverse) and was copied whole; "
    "(2) if the key is restricted to trusted IP addresses, THIS machine's outbound address "
    "is on the list. The restriction is per address, not per key; the address the exchange "
    "sees can differ from the one in the provider's panel, and a host with IPv6 may go out "
    "over IPv6 while only IPv4 is listed; "
    "(3) the key has the permission asked for (Enable Reading, and trading for a trading venue) "
    "and the change is saved."
)


def address_in(reply: str) -> str | None:
    """The address a `-2015` reply names, if it parses as one."""
    found = _REQUEST_IP.search(reply)
    if found is None:
        return None
    try:
        return str(ipaddress.ip_address(found.group(1).rstrip(".")))
    except ValueError:
        return None


def describe_address(address: str | None) -> str:
    if address is None:
        return "the exchange did not report the address it saw"
    family = f"IPv{ipaddress.ip_address(address).version}"
    return f"the exchange saw {address} ({family})"


class OutboundAddressCheck(PerVenueCheck):
    check_id = "outbound-address"
    title = "Exchange accepts this machine's address"

    def look_at(
        self, scope: PreflightScope, name: str, context: VenueContext
    ) -> CheckFinding:
        status = self._reads.connection(scope, name, context)
        if status.failure is ConnectionFailureKind.KEY_REJECTED:
            seen = self._address_seen(scope, name, context)
            return CheckFinding(
                name,
                CheckStatus.FAIL,
                f"the exchange rejected the key (-2015 family); {describe_address(seen)}",
                CHECKLIST,
                CheckCause.CREDENTIALS,
            )
        if status.reachable or status.server_time_skew_ms is not None:
            return CheckFinding(
                name,
                CheckStatus.PASS,
                "the exchange accepted the key from this machine's address",
            )
        return unreadable_connection(name, status, "the address check")

    def _address_seen(
        self, scope: PreflightScope, name: str, context: VenueContext
    ) -> str | None:
        if not context.venue.is_mainnet:
            return None
        verdict = self._reads.mainnet_verdict(scope, name, context)
        return None if verdict is None else address_in(verdict.reason)
