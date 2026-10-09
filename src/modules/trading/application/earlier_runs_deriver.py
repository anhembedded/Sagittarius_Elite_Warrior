"""`BUG-196` — the owner's inventory from before the current run began.

@details The same replay as `OwnerInventoryDeriver` (tagged orders joined to
their trades by the exchange order id, base-asset fees netted), over the
owner's whole readable history but stopping at `until`. It keeps no checkpoint
and installs nothing: the registration's checkpoint belongs to the current run,
and this read must never replace it.
"""

from __future__ import annotations

import logging
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_inventory_deriver import (
    owner_fill_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsInventory,
    EarlierRunsRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    MAX_HISTORY_LOOKBACK,
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    EMPTY_INVENTORY,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.owner_inventory_policy import (
    inventory_after,
)

logger = logging.getLogger("App.Trading.OwnerInventory")


def derive_earlier_runs(
    request: EarlierRunsRequest, history: IAccountHistoryReader, now: datetime
) -> EarlierRunsInventory:
    """@brief The base `request`'s owner bought and still held when its current
    run began, from the venue's history; not yet capped by the account.
    @throws AccountHistoryUnavailableError The venue did not answer."""
    read_from = max(request.since, now - MAX_HISTORY_LOOKBACK)
    owned = {
        record.exchange_order_id
        for record in history.order_history(request.symbol, read_from)
        if tag_of(str(record.order.client_order_id)) == request.tag
    }
    inventory = EMPTY_INVENTORY
    for trade in history.trade_history(request.symbol, read_from):
        if trade.order_id in owned and trade.time < request.until:
            inventory = inventory_after(
                inventory, owner_fill_of(trade, request.base_asset)
            )
    logger.info(
        "[earlier-runs] %s on %s: %s %s before %s (read from %s).",
        request.tag,
        request.symbol,
        inventory.quantity,
        request.base_asset,
        request.until.isoformat(),
        read_from.isoformat(),
    )
    return EarlierRunsInventory(inventory.quantity, inventory.cost, read_from)
