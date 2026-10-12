"""The pre-flight checks `trading` owns, as the declarations `TradingModule` hands over (`EPIC-038F`).

`trading` knows the key, its permissions and the clock the exchange keeps, so it
owns these five; `operations` owns the machine's own. A sixth is one class and
one tuple entry here.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    PortResolver,
    PreflightCheckDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_preflight_check import (
    IPreflightCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.clock_skew_check import (
    ClockSkewCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.credentials_present_check import (
    CredentialsPresentCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.key_permissions_check import (
    KeyPermissionsCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.no_withdraw_permission_check import (
    NoWithdrawPermissionCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.outbound_address_check import (
    OutboundAddressCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_checks import (
    PerVenueCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_reads import (
    VenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_environment_probe import (
    IKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)

_CHECKS: tuple[tuple[str, Callable[[VenueReads], PerVenueCheck]], ...] = (
    ("clock-skew", ClockSkewCheck),
    ("credentials-present", CredentialsPresentCheck),
    ("key-permissions", KeyPermissionsCheck),
    ("no-withdraw-permission", NoWithdrawPermissionCheck),
    ("outbound-address", OutboundAddressCheck),
)


def _factory(
    build: Callable[[VenueReads], PerVenueCheck],
) -> Callable[[PortResolver], IPreflightCheck]:
    def make(resolver: PortResolver) -> IPreflightCheck:
        # mypy cannot pass an abstract port to `type[T]`; the container resolves it.
        contexts = resolver.resolve(IVenueContexts)  # type: ignore[type-abstract]
        probe = resolver.resolve(IKeyEnvironmentProbe)  # type: ignore[type-abstract]
        return build(VenueReads(contexts, probe))

    return make


def trading_preflight_checks(
    contributor_id: str,
) -> tuple[PreflightCheckDescriptor, ...]:
    return tuple(
        PreflightCheckDescriptor(check_id, _factory(build), contributor_id)
        for check_id, build in _CHECKS
    )
