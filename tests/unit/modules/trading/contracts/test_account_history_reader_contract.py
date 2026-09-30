"""`IAccountHistoryReader`'s contract, against its verified fake (HLD §10.3).

The real `FuturesHistoryReader` and `SpotHistoryReader` read through the fake
exchange server in `tests/integration/infrastructure/binance/`.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.contract_account_history_reader import (
    AccountHistoryReaderContract,
    GivenHistory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_history_reader import (
    FakeAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)


class TestFakeAccountHistoryReader(AccountHistoryReaderContract):
    @pytest.fixture
    def given_history(self) -> GivenHistory:
        def given(
            orders: Sequence[OrderRecord], trades: Sequence[TradeRecord]
        ) -> IAccountHistoryReader:
            return FakeAccountHistoryReader(orders, trades)

        return given
