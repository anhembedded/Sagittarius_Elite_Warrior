"""`BOT-206` — the Plan's property table, one frame per state worth looking at.

Offline, like `preview.py`: the screen is filled directly from a bot snapshot, so every word on a
frame is the one the screen writes (`bot_facts`, `ladder_facts`, `readiness_words`). The window is
tall enough for the Plan to show its whole table without scrolling, which is the point of a
frame the owner looks at (`ui-presentation-rule.md` §5):

  draft_blocked · futures_running · spot_running · spot_waiting · futures_short_waiting

Run one with `python -m Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_table_frames
<frame> [--png path]` (offscreen with `--png`, a window otherwise).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from PySide6.QtWidgets import QApplication, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    grid_ladder_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_pnl import PnlSummary
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
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

_NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)
_SYMBOL = "BTCUSDT"
_RANGE = {
    "lower": "60000",
    "upper": "70000",
    "grid_count": "10",
    "spacing": "ARITHMETIC",
    "stop_loss": "percent:5",
    "take_profit": "off",
}
#: The frames' window: tall enough that the Plan shows the whole table.
_WINDOW = (1360, 1500)


def _bot(
    venue: TradingVenue,
    state: BotLifecycleState,
    config: dict[str, str],
    progress: BotProgress | None,
) -> BotSnapshot:
    return BotSnapshot(
        bot_id="p00001",
        name=f"BTC grid {venue.display_name.lower()}",
        kind="grid",
        venue=venue,
        symbol=_SYMBOL,
        state=state,
        created_at=_NOW - timedelta(days=2),
        run_started_at=None if progress is None else _NOW - timedelta(hours=30),
        config=config,
        progress=progress,
    )


def _screen(
    bot: BotSnapshot,
    readiness: BotReadiness | None = None,
    verdicts: tuple[Verdict, ...] = (),
) -> BotsView:
    """The Bots screen with `bot` selected, as the presenter would have filled it."""
    view = BotsView()
    view.model.set_bots((bot,))
    view.model.set_selected(bot)
    view.model.set_facts(bot_facts(bot, _NOW))
    view.model.set_ladder(grid_ladder_of(bot, _NOW))
    view.model.set_availability(
        {
            action: availability(bot.state, action, StartConditions())
            for action in BotAction
        }
    )
    if readiness is not None:
        view.model.set_readiness(readiness, ReadinessState.DESIGNING)
    panel = GridPanel()
    profile = venue_profile_of(bot.venue)
    if profile is not None:
        panel.set_profile(profile)
    panel.set_config(bot.config)
    panel.show_verdicts(verdicts)
    view.set_kind_panel(panel)
    view.apply_ui_mode(
        BotsUiState.EDITING_DRAFT
        if bot.state is BotLifecycleState.DRAFT
        else BotsUiState.VIEWING
    )
    view.resize(*_WINDOW)
    return view


def _pnl(
    realised: str,
    unrealised: str,
    commissions: str = "0",
    funding: str = "0",
) -> PnlSummary:
    return PnlSummary(
        total=Decimal(realised) + Decimal(unrealised),
        realised=Decimal(realised),
        unrealised=Decimal(unrealised),
        grid_profit=Decimal(realised),
        hodl=Decimal("-18.40"),
        unpriced_fees=0,
        commissions=Decimal(commissions),
        funding=Decimal(funding),
    )


def _draft_blocked() -> BotsView:
    """A new Spot draft whose capital is above the balance: Design has one thing left, and the
    reason stands above the table with its sign."""
    capital = ReadinessItem(
        ReadinessStep.DESIGN,
        "CAPITAL_ABOVE_BALANCE",
        "The capital is 1000 USDT, above the 800.00 USDT available on Spot Testnet; "
        "lower it to at most 800.00",
        ReadinessFix.EDIT_FIELD,
        BotRefusal.PARAMETERS_REFUSED,
        "CAPITAL_ABOVE_BALANCE",
    )
    readiness = BotReadiness(
        (
            StepReadiness(ReadinessStep.CONNECT, StepStatus.DONE),
            StepReadiness(ReadinessStep.DESIGN, StepStatus.OPEN, (capital,)),
            StepReadiness(ReadinessStep.RUN, StepStatus.WAITING),
        )
    )
    verdicts = (
        Verdict(VerdictSeverity.REFUSED, capital.code, capital.reason),
        Verdict(
            VerdictSeverity.WARNING,
            "RANGE_OUTSIDE_ATR_BAND",
            "The range is narrower than two daily ATRs",
        ),
    )
    bot = _bot(
        TradingVenue.SPOT_TESTNET,
        BotLifecycleState.DRAFT,
        {**_RANGE, "capital_quote": "1000"},
        None,
    )
    return _screen(bot, readiness, verdicts)


def _futures_running() -> BotsView:
    """A running Long Futures bot holding a position, with costs, a heard price and a liquidation row."""
    progress = BotProgress(
        realised_profit=Decimal("41.20"),
        completed_cycles=9,
        open_orders=4,
        inventory=Decimal("0.0615"),
        average_cost=Decimal(63100),
        reason="",
        reason_detail="",
        mark_price=Decimal(64200),
        mark_price_at=_NOW - timedelta(seconds=40),
        pnl=_pnl("41.20", "67.65", commissions="1.3726", funding="-2.7000"),
    )
    config = {
        **_RANGE,
        "capital_quote": "10000",
        "direction": "LONG",
        "leverage": "3",
    }
    return _screen(
        _bot(TradingVenue.FUTURES_TESTNET, BotLifecycleState.RUNNING, config, progress)
    )


def _spot_running() -> BotsView:
    """A running Spot bot: no cost rows, no liquidation row, the readiness group gone."""
    progress = BotProgress(
        realised_profit=Decimal("12.50"),
        completed_cycles=3,
        open_orders=2,
        inventory=Decimal("0.0031"),
        average_cost=Decimal(64000),
        reason="",
        reason_detail="",
        mark_price=Decimal(64500),
        mark_price_at=_NOW - timedelta(minutes=2),
        pnl=_pnl("12.50", "1.55"),
    )
    config = {**_RANGE, "capital_quote": "500"}
    return _screen(
        _bot(TradingVenue.SPOT_TESTNET, BotLifecycleState.RUNNING, config, progress)
    )


def _waiting_progress(price: str) -> BotProgress:
    """A run that has placed nothing and holds nothing, and has heard `price`."""
    return BotProgress(
        realised_profit=Decimal(0),
        completed_cycles=0,
        open_orders=0,
        inventory=Decimal(0),
        average_cost=None,
        reason="",
        reason_detail="",
        mark_price=Decimal(price),
        mark_price_at=_NOW - timedelta(seconds=12),
    )


def _spot_waiting() -> BotsView:
    """`EPIC-044C`: a Spot bot started below its range: it waits, with nothing placed (ADR 044)."""
    config = {**_RANGE, "capital_quote": "500"}
    return _screen(
        _bot(
            TradingVenue.SPOT_TESTNET,
            BotLifecycleState.AWAITING_RANGE,
            config,
            _waiting_progress("58250"),
        )
    )


def _futures_short_waiting() -> BotsView:
    """`EPIC-044C`: a Short Futures bot started above its range: it does not sell short before the
    price is inside (the defect ADR 044 closes)."""
    config = {
        **_RANGE,
        "capital_quote": "10000",
        "direction": "SHORT",
        "leverage": "3",
    }
    return _screen(
        _bot(
            TradingVenue.FUTURES_TESTNET,
            BotLifecycleState.AWAITING_RANGE,
            config,
            _waiting_progress("71400"),
        )
    )


FRAMES: Mapping[str, Callable[[], BotsView]] = {
    "draft_blocked": _draft_blocked,
    "futures_running": _futures_running,
    "spot_running": _spot_running,
    "spot_waiting": _spot_waiting,
    "futures_short_waiting": _futures_short_waiting,
}


def build_frame(name: str) -> QWidget:
    """@raise KeyError `name` is not one of `FRAMES`."""
    return FRAMES[name]()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One frame of the Bots screen's Plan property table."
    )
    parser.add_argument("frame", choices=sorted(FRAMES))
    parser.add_argument(
        "--png", metavar="PATH", help="Save the frame instead of showing it."
    )
    args = parser.parse_args()
    app = QApplication.instance() or QApplication(sys.argv)
    widget = build_frame(args.frame)
    if args.png:
        widget.show()
        # The rows ask for the height of their wrapped text once the window has its width, and the
        # layout that makes room for it is a second pass.
        for _ in range(3):
            app.processEvents()
        widget.grab().save(args.png)
        return
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
