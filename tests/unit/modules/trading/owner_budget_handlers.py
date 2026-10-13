"""The real `RegisterOwnerBudgetCommandHandler`, built the way the composition
root builds it, for the tests that register a budget over a venue scope."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_inventory_deriver import (
    OwnerInventoryDeriver,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_position_deriver import (
    OwnerPositionDeriver,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_position_registrar import (
    OwnerPositionRegistrar,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.register_owner_budget import (
    RegisterOwnerBudgetCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_owner_inventory_checkpoints import (
    FakeOwnerInventoryCheckpoints,
)


def registration_handler(
    scopes: VenueTradingScopes, caps: OwnerBudgetCaps = DEFAULT_OWNER_BUDGET_CAPS
) -> RegisterOwnerBudgetCommandHandler:
    return RegisterOwnerBudgetCommandHandler(
        scopes,
        OwnerInventoryDeriver(FakeOwnerInventoryCheckpoints()),
        OwnerPositionRegistrar(OwnerPositionDeriver()),
        caps,
    )
