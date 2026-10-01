"""`EPIC-028B` — the verified fake for `IVenueTradingPorts`.

@details Serves exactly the venues it is given, each with the fakes a test
arranges (a `FakeTradingSession` reporting Spot, a `FakeOrderSubmission`
recording what was sent), and follows the port's own rules: `DISABLED` only
while it is the primary venue, any other unserved venue refused with
`VenueNotEnabledError`. `VenueTradingPortsContract` holds it to those rules
alongside the real registry.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_activity import (
    IAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_equity_curve import (
    IEquityCurve,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_settings_control import (
    IFuturesSettingsControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_entry_terms import (
    IOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_activity import (
    FakeAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_equity_curve import (
    FakeEquityCurve,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_futures_settings_control import (
    FakeFuturesSettingsControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def fake_venue_ports(
    venue: TradingVenue,
    *,
    trading_session: ITradingSession | None = None,
    order_submission: IOrderSubmission | None = None,
    account_snapshot: IAccountSnapshot | None = None,
    equity_curve: IEquityCurve | None = None,
    order_entry_terms: IOrderEntryTerms | None = None,
    account_activity: IAccountActivity | None = None,
    futures_settings: IFuturesSettingsControl | None = None,
) -> VenueTradingPorts:
    """One venue's bundle, every port a fake unless the test hands one in."""
    return VenueTradingPorts(
        venue=venue,
        order_submission=order_submission or FakeOrderSubmission(),
        trading_session=trading_session or FakeTradingSession(),
        account_snapshot=account_snapshot or FakeAccountSnapshot(),
        equity_curve=equity_curve or FakeEquityCurve(),
        order_entry_terms=order_entry_terms or FakeOrderEntryTerms(),
        account_activity=account_activity or FakeAccountActivity(),
        futures_settings=futures_settings or FakeFuturesSettingsControl(),
    )


class FakeVenueTradingPorts(IVenueTradingPorts):
    """The venues a test says are served; the first one is primary."""

    def __init__(self, *ports: VenueTradingPorts) -> None:
        self._ports = {bundle.venue: bundle for bundle in ports}
        self._primary = ports[0]

    def enabled(self) -> tuple[TradingVenue, ...]:
        return tuple(v for v in self._ports if v is not TradingVenue.DISABLED)

    def get(self, venue: TradingVenue) -> VenueTradingPorts:
        bundle = self._ports.get(venue)
        if bundle is None or (
            venue is TradingVenue.DISABLED and self._primary.venue is not venue
        ):
            raise VenueNotEnabledError(venue, self.enabled())
        return bundle

    def primary(self) -> VenueTradingPorts:
        return self._primary
