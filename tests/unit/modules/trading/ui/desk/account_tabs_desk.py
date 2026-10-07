"""`EPIC-028J` — one Futures desk's account tabs over verified fakes, shared
by the presenter's loading/event tests and its action tests.

@details Every port is a verified fake from `contracts/testing`; the bus is
the engine's real `MemoryEventBus` behind the real `OrderFeed`; the worker
pool runs inline unless a test hands in a held one."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_activity import (
    FakeAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tab_confirmations import (
    AccountTabConfirmations,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tabs_panel import (
    AccountTabsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tabs_presenter import (
    AccountTabsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    HeldTab,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)

from .account_tabs_fixtures import NOW
from .order_entry_fixtures import InlineThreadManager

FUTURES = TradingVenue.FUTURES_TESTNET


class AccountTabsDesk:
    """One Futures desk's tabs over fakes, every dialog answered Yes."""

    def __init__(self, qtbot, threads=None) -> None:
        self.now = NOW
        self.bus = MemoryEventBus()
        self.activity = FakeAccountActivity()
        self.snapshot = FakeAccountSnapshot()
        self.submission = FakeOrderSubmission()
        self.threads = threads or InlineThreadManager()
        self.notifier = RecordingNotifier()
        self.panel = AccountTabsPanel(
            HeldTab.POSITIONS,
            AccountTabConfirmations(
                cancel_one=lambda _r: True,
                cancel_all=lambda _r: True,
                close_position=lambda _r: True,
            ),
        )
        qtbot.addWidget(self.panel)
        self.presenter = AccountTabsPresenter(
            self.panel,
            fake_venue_ports(
                FUTURES,
                account_activity=self.activity,
                account_snapshot=self.snapshot,
                order_submission=self.submission,
            ),
            OrderFeed(self.bus, FUTURES, parent=self.panel),
            self.threads,
            self.notifier,
            clock=lambda: self.now,
        )

    def open_order_ids(self) -> list[str]:
        model = self.panel.open_orders_panel.table.model().sourceModel()
        return sorted(row.client_order_id for row in model.rows)

    def position_symbols(self) -> list[str]:
        model = self.panel.positions_panel.table.model().sourceModel()
        return sorted(row.symbol for row in model.rows)

    def message(self) -> str:
        return self.panel.message_text
