"""`EPIC-039E` — a Futures venue a test can ask: a symbol that keeps the settings it is given.

@details Built from the verified fakes of `trading/contracts/testing`, not from the calls the
gate makes: `FakeOrderEntryTerms` answers the reads, and the control below is the real fake
control plus the one thing the venue does that the fake does not, remember what it applied
(so a read-back sees it). `silently_ignores_changes` is the venue that answers success and
changes nothing, the case read-back exists for.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import override

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FakeBotClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_unavailable_error import (
    AccountControlUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    FuturesAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_setting import (
    LeverageSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import (
    OrderType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_activity import (
    FakeAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_futures_settings_control import (
    FakeFuturesSettingsControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
    FuturesReads,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
    RUN_STARTED,
)

FUTURES = TradingVenue.FUTURES_TESTNET
SYMBOL = "BTCUSDT"
AVAILABLE_MARGIN = Decimal(10_000)

#: The first bracket allows 20x up to 50 000 notional, the second 10x up to 250 000.
BRACKETS = LeverageBrackets(
    SYMBOL,
    (
        LeverageBracket(
            1, 20, Decimal(0), Decimal(50_000), Decimal("0.004"), Decimal(0)
        ),
        LeverageBracket(
            2, 10, Decimal(50_000), Decimal(250_000), Decimal("0.005"), Decimal(50)
        ),
    ),
)


def a_futures_status(
    mode: PositionMode = PositionMode.ONE_WAY,
    available: Decimal = AVAILABLE_MARGIN,
) -> ExchangeConnectionStatus:
    summary = FuturesAccountSummary(
        venue=FUTURES,
        available_balance=available,
        equity=available,
        wallet_balance=available,
        margin_balance=available,
        unrealized_pnl=Decimal(0),
        position_mode=mode,
    )
    return ExchangeConnectionStatus(
        venue=FUTURES,
        reachable=True,
        failure=None,
        server_time_skew_ms=0,
        usdt_balance=available,
        position_mode=mode,
        margin_type=None,
        open_position_count=0,
        summary=summary,
        can_trade=True,
    )


class MovableTerms(FakeOrderEntryTerms):
    """The venue's order-entry reads, whose symbol setting a test (or a change) can move."""

    def __init__(self, setting: FuturesSymbolSetting) -> None:
        super().__init__(
            futures=FuturesReads(
                settings={setting.symbol: setting}, brackets={setting.symbol: BRACKETS}
            )
        )
        self.setting = setting
        #: The venue never answers the settings read.
        self.unreadable = False

    @override
    def futures_setting_for(self, symbol: str) -> FuturesSymbolSetting | NotApplicable:
        if self.unreadable:
            raise AccountControlUnavailableError(f"{symbol}'s settings timed out")
        return self.setting


class RememberingSettings(FakeFuturesSettingsControl):
    """The control of a venue whose symbol keeps what it was last given."""

    def __init__(self, terms: MovableTerms, setting: FuturesSymbolSetting) -> None:
        super().__init__()
        self._terms = terms
        self.setting = setting
        self.silently_ignores_changes = False
        #: Every method name called, so a test can assert what the gate never calls.
        self.calls: list[str] = []

    def move(self, **changes: object) -> None:
        """Someone changes the symbol in the Binance app: no gate call involved."""
        self.setting = replace(self.setting, **changes)  # type: ignore[arg-type]
        self._terms.setting = self.setting

    @override
    def change_leverage(
        self, symbol: str, leverage: int
    ) -> AccountControlResult[LeverageSetting]:
        self.calls.append("change_leverage")
        answer = super().change_leverage(symbol, leverage)
        if answer.applied is not None and not self.silently_ignores_changes:
            self.move(leverage=leverage)
        return answer

    @override
    def change_margin_type(
        self, symbol: str, margin_type: MarginType
    ) -> AccountControlResult[MarginType]:
        self.calls.append("change_margin_type")
        answer = super().change_margin_type(symbol, margin_type)
        if answer.applied is not None and not self.silently_ignores_changes:
            self.move(margin_type=margin_type)
        return answer


class FuturesWorld:
    """A Futures venue, its ports and the bot that runs on it."""

    def __init__(
        self,
        leverage: int = 5,
        margin_type: MarginType = MarginType.CROSSED,
        status: ExchangeConnectionStatus | None = None,
    ) -> None:
        setting = FuturesSymbolSetting(
            SYMBOL, leverage, margin_type, Decimal(1_000_000)
        )
        self.terms = MovableTerms(setting)
        self.settings = RememberingSettings(self.terms, setting)
        self.account = FakeAccountSnapshot(status or a_futures_status())
        self.activity = FakeAccountActivity()
        self.ports = FakeVenueTradingPorts(
            fake_venue_ports(
                FUTURES,
                account_snapshot=self.account,
                account_activity=self.activity,
                order_entry_terms=self.terms,
                futures_settings=self.settings,
            )
        )
        self.clock = FakeBotClock()
        self.bot = Bot(
            BotId(BOT),
            BotDefinition("grid one", "grid", FUTURES, SYMBOL, CONFIG),
            BotLifecycle(BotLifecycleState.DRAFT, RUN_STARTED, None),
            RUN_STARTED,
        )

    def rests_an_order(self, tag: str | None = None) -> None:
        prefix = f"SEW-{tag}-" if tag else "SEW-"
        self.activity.holding_open_orders(
            [
                Order(
                    client_order_id=ClientOrderId(
                        f"{prefix}{'a' * (10 if tag else 12)}"
                    ),
                    symbol=SYMBOL,
                    side=OrderSide.BUY,
                    order_type=OrderType.LIMIT,
                    quantity=Decimal("0.01"),
                    price=Decimal(60_000),
                )
            ]
        )

    def holds_a_position(self, amount: str) -> None:
        self.account.holding(
            [
                LivePosition(
                    symbol=SYMBOL,
                    position_amt=Decimal(amount),
                    entry_price=Decimal(60_000),
                    mark_price=Decimal(60_000),
                    unrealized_pnl=Decimal(0),
                    leverage=5,
                    margin_type=MarginType.CROSSED,
                    liquidation_price=None,
                    updated_at=RUN_STARTED,
                )
            ]
        )
