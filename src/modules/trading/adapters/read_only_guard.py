"""`EPIC-035H` — the one place a venue's exchange doors are made read-only.

A venue has two ways to change the account: orders (a trading client from its
factory) and Futures leverage / margin mode (its account control). Each is
wrapped here when the instance is read-only and handed back as it is otherwise,
so `VenueAssembly` asks one question in one place and a third door is one more
function here.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.read_only_account_control import (
    ReadOnlyAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.read_only_trading_client_factory import (
    ReadOnlyTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_account_control import (
    IFuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)


def guarded_client_factory(
    factory: ITradingClientFactory, instance: IInstanceAccess
) -> ITradingClientFactory:
    """`factory`, or its read-only wrapper when `instance` is read-only."""
    if instance.read_only:
        return ReadOnlyTradingClientFactory(factory, instance.reason)
    return factory


def guarded_account_control(
    control: IFuturesAccountControl, instance: IInstanceAccess
) -> IFuturesAccountControl:
    """`control`, or its read-only wrapper when `instance` is read-only."""
    if instance.read_only:
        return ReadOnlyAccountControl(control, instance.reason)
    return control
