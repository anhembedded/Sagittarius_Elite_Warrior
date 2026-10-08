"""`EPIC-029F` — the Bots screen with a sample bot in every lifecycle state.

Offline: the view model is filled directly, no container, no engine, no
network. The selected bot is a draft, so its parameters are editable and its
verdicts are shown; the chart is left out, the bot chart's own preview shows
it (`bots/ui/chart/preview.py`).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotOrderLine,
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
    ReadinessFix,
    ReadinessItem,
    ReadinessStep,
    StepReadiness,
    StepStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
    StartConditions,
    availability,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    bot_facts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_ui_fsm_matrix import (
    BotsUiState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_NOW = datetime(2026, 10, 4, 12, tzinfo=UTC)
_CONFIG = {
    "lower": "60000",
    "upper": "70000",
    "grid_count": "10",
    "spacing": "ARITHMETIC",
    "capital_quote": "1000",
    "stop_loss": "percent:5",
    "take_profit": "off",
}


def build_preview() -> QWidget:
    view = BotsView()
    bots = tuple(_bot(index, state) for index, state in enumerate(BotLifecycleState))
    view.model.set_bots(bots)
    draft = bots[0]
    view.model.set_selected(draft)
    view.model.set_facts(bot_facts(draft, _NOW))
    view.model.set_judgement(
        (
            "OK: Every grid earns more than its fees (thinnest step 0.0145, fees 0.002)",
            "Warning: The range is narrower than two daily ATRs (range 10000, threshold 11400)",
        )
    )
    view.model.set_readiness(_sample_readiness(), ReadinessState.DESIGNING, True)
    view.model.set_availability(
        {
            action: availability(draft.state, action, StartConditions())
            for action in BotAction
        }
    )
    panel = GridPanel()
    panel.set_config(draft.config)
    view.set_kind_panel(panel)
    view.apply_ui_mode(BotsUiState.EDITING_DRAFT)
    view.resize(1200, 760)
    return view


def _sample_readiness() -> BotReadiness:
    """A draft whose capital is above the balance: Design has one thing left."""
    capital = ReadinessItem(
        ReadinessStep.DESIGN,
        "CAPITAL_ABOVE_BALANCE",
        "The capital is 1000 USDT, above the 800.00 USDT available on Spot Testnet; "
        "lower it to at most 800.00",
        ReadinessFix.EDIT_FIELD,
        BotRefusal.PARAMETERS_REFUSED,
        "CAPITAL_ABOVE_BALANCE",
    )
    return BotReadiness(
        (
            StepReadiness(ReadinessStep.CONNECT, StepStatus.DONE),
            StepReadiness(ReadinessStep.DESIGN, StepStatus.OPEN, (capital,)),
            StepReadiness(ReadinessStep.RUN, StepStatus.WAITING),
        )
    )


def _bot(index: int, state: BotLifecycleState) -> BotSnapshot:
    ran = state not in (BotLifecycleState.DRAFT,)
    return BotSnapshot(
        bot_id="a" + str(index).zfill(5),
        name=f"BTC grid {state.value.lower()}",
        kind="grid",
        venue=TradingVenue.SPOT_TESTNET,
        symbol="BTCUSDT",
        state=state,
        created_at=_NOW - timedelta(days=3),
        run_started_at=_NOW - timedelta(hours=26) if ran else None,
        config=_CONFIG,
        progress=_progress(index) if ran else None,
    )


def _progress(index: int) -> BotProgress:
    return BotProgress(
        realised_profit=Decimal("12.5") * index,
        completed_cycles=index,
        open_orders=2,
        inventory=Decimal("0.0031"),
        average_cost=Decimal(64000),
        reason="",
        reason_detail="",
        orders=(
            BotOrderLine(
                4,
                "BUY",
                Decimal(64000),
                Decimal("0.0015"),
                Decimal(0),
                "SEW-a00000-0000000001",
            ),
            BotOrderLine(
                6,
                "SELL",
                Decimal(66000),
                Decimal("0.0015"),
                Decimal("0.0005"),
                "SEW-a00000-0000000002",
            ),
        ),
    )
