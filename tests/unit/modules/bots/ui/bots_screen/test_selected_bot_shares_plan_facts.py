"""`BUG-211` — the editor judges its suggestions with the facts the screen judges the plan
with: the risk the venue gave reaches the Grid editor, and none clears it."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)

from .bots_screen_fixtures import BotLifecycleState, stored

_FACTS = PlanRiskFacts(
    FuturesSymbolSetting("BTCUSDT", 3, MarginType.ISOLATED, Decimal(10**9)),
    LeverageBrackets(
        "BTCUSDT",
        (
            LeverageBracket(
                1, 125, Decimal(0), Decimal(10**9), Decimal("0.004"), Decimal(0)
            ),
        ),
    ),
)


class _RecordingPanel(GridPanel):
    def __init__(self) -> None:
        super().__init__()
        self.heard: list[tuple[AccountView | None, PlanRiskFacts | None]] = []

    def set_plan_facts(
        self, account: AccountView | None, risk: PlanRiskFacts | None
    ) -> None:
        self.heard.append((account, risk))
        super().set_plan_facts(account, risk)


def _selected(commands: ICommandDispatcher) -> SelectedBot:
    return SelectedBot(
        BotKindCatalog(()), lambda: datetime(2026, 10, 4, tzinfo=UTC), commands
    )


def test_the_risk_the_venue_gave_reaches_the_editor_and_none_clears_it(
    open_bots_screen, qtbot
) -> None:
    screen = open_bots_screen([stored("a00001", BotLifecycleState.DRAFT)])
    screen.settle()
    selected = _selected(screen.dispatcher)
    selected.select(screen.view.model.bots[0])
    panel = _RecordingPanel()
    qtbot.addWidget(panel)
    selected.panel = panel

    selected.take_risk(_FACTS)

    assert panel.heard[-1] == (None, _FACTS)
    selected.take_risk(None)
    assert panel.heard[-1] == (None, None)
