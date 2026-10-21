"""`BOT-209` — the Plan's status banner and checks, one frame per state worth looking at.

Offline, like `preview.py`: the screen is filled directly, the verdicts are the real planner's
(`evaluate_grid` over an ETHUSDT Futures plan) and the readiness item is worded as the Futures rules
word it, so every sentence on a frame is the one a person would read:

  blocked_by_held_position · thin_step_warning · ready_draft · running_bot · unsaved_design

Run one with `python -m Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_dock_frames
<frame> [--png path] [--size WxH]` (offscreen with `--png`, a window otherwise).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping
from dataclasses import replace
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureLimits,
    VenueProfile,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    ExchangeTerms,
    MarketView,
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_pnl import PnlSummary
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
    StartConditions,
    availability,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_detail import (
    DetailInputs,
    detail_for,
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
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_checks import (
    plan_checks_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_liquidation import (
    liquidation_lines,
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)
_VENUE = TradingVenue.FUTURES_TESTNET
_SYMBOL = "ETHUSDT"
_LAST = Decimal("2425.86")
_FAILURE = (
    "L14 SELL: the request failed (OrderRejectedByExchangeError); see the log; "
    "any position is closed at market"
)
_HELD = (
    "ETHUSDT already holds a long position of 0.308 on Futures Testnet; a bot starts on a "
    "flat symbol, so close it first"
)
_TERMS = ExchangeTerms(
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.001"),
    min_notional=Decimal(20),
    maker_fee=Decimal("0.0002"),
    taker_fee=Decimal("0.0005"),
    max_notional_per_order=Decimal(50000),
    max_open_orders=200,
)
_BRACKETS = LeverageBrackets(
    _SYMBOL,
    (
        LeverageBracket(
            1, 125, Decimal(0), Decimal(50_000), Decimal("0.004"), Decimal(0)
        ),
        LeverageBracket(
            2, 100, Decimal(50_000), Decimal(250_000), Decimal("0.005"), Decimal(50)
        ),
    ),
)
_PLAN = {
    "lower": "2200",
    "upper": "2700",
    "spacing": "ARITHMETIC",
    "capital_quote": "2000",
    "stop_loss": "percent:5",
    "take_profit": "percent:5",
    "direction": "LONG",
    "leverage": "3",
}
#: A thin step: 60 grids over a 500-wide range, 0.34 % at the top.
_THIN = {**_PLAN, "grid_count": "60"}
_FINE = {**_PLAN, "grid_count": "20"}
_WINDOW = (1360, 1500)


def _profile() -> VenueProfile:
    profile = venue_profile_of(_VENUE)
    if profile is None:
        raise LookupError(f"{_VENUE.display_name} has no venue profile to preview")
    return profile


def _verdicts(config: Mapping[str, str]) -> tuple[Verdict, ...]:
    """What the planner says about `config` on the Futures testnet."""
    profile = _profile()
    facts = PlanRiskFacts(
        FuturesSymbolSetting(
            _SYMBOL, int(config["leverage"]), MarginType.ISOLATED, Decimal(10**9)
        ),
        _BRACKETS,
    )
    inputs = BotKindInputs(
        config,
        _TERMS,
        MarketView(_LAST, Decimal(110), base_asset="ETH", quote_asset="USDT"),
        None,
        ExposureLimits(profile.directions, profile.max_leverage),
        facts,
    )
    return evaluate_grid(inputs, GridThresholds()).verdicts


def _bot(
    state: BotLifecycleState,
    config: dict[str, str],
    progress: BotProgress | None = None,
) -> BotSnapshot:
    return BotSnapshot(
        bot_id="e00001",
        name="ETH futures grid",
        kind="grid",
        venue=_VENUE,
        symbol=_SYMBOL,
        state=state,
        created_at=_NOW - timedelta(days=2),
        run_started_at=None
        if state is BotLifecycleState.DRAFT
        else _NOW - timedelta(hours=30),
        config=config,
        progress=progress,
    )


def _readiness(*run_items: ReadinessItem) -> BotReadiness:
    return BotReadiness(
        (
            StepReadiness(ReadinessStep.CONNECT, StepStatus.DONE),
            StepReadiness(ReadinessStep.DESIGN, StepStatus.DONE),
            StepReadiness(
                ReadinessStep.RUN,
                StepStatus.OPEN if run_items else StepStatus.DONE,
                run_items,
            ),
        )
    )


def _screen(
    bot: BotSnapshot,
    readiness: BotReadiness | None,
    state: ReadinessState,
    design: Mapping[str, str] | None = None,
) -> BotsView:
    """`design`: the parameters on screen when they are not the saved ones (`BUG-261`); the
    figures are then the detail's own, as the screen computes them."""
    view = BotsView()
    view.model.set_bots((bot,))
    view.model.set_selected(bot)
    detail = detail_for(DetailInputs(bot, None, None, _NOW, edited=design))
    verdicts = _verdicts(design or bot.config)
    facts = detail.facts
    if design is not None:
        # `detail_for` judges with the kind's inputs, which a frame has no catalog for: the
        # frame's own verdicts say the liquidation estimate the screen would.
        facts = replace(
            facts,
            liquidation_estimate="; ".join(
                line.text for line in liquidation_lines(verdicts)
            ),
        )
    view.model.set_facts(facts)
    view.model.set_ladder(detail.ladder)
    view.model.set_judgement(plan_checks_of(verdicts))
    view.model.set_availability(
        {
            action: availability(bot.state, action, StartConditions())
            for action in BotAction
        }
    )
    panel = GridPanel()
    panel.set_profile(_profile())
    panel.set_config(design or bot.config)
    panel.show_verdicts(verdicts)
    view.set_kind_panel(panel)
    if readiness is not None:
        view.model.set_readiness(readiness, state)
    view.apply_ui_mode(
        BotsUiState.EDITING_DRAFT
        if bot.state is BotLifecycleState.DRAFT
        else BotsUiState.VIEWING
    )
    view.resize(*_WINDOW)
    return view


def _blocked_by_held_position() -> BotsView:
    """A draft that failed once and now meets a position it did not open: the banner says what
    stands in Start's way and how the last run ended, and the thin step stays advice."""
    held = ReadinessItem(
        ReadinessStep.RUN,
        "RUN_FOREIGN_POSITION",
        _HELD,
        ReadinessFix.NONE,
        BotRefusal.VENUE_NOT_READY,
    )
    progress = BotProgress(
        realised_profit=Decimal(0),
        completed_cycles=0,
        open_orders=0,
        inventory=Decimal(0),
        average_cost=Decimal(0),
        reason="start_failed",
        reason_detail=_FAILURE,
    )
    bot = _bot(BotLifecycleState.DRAFT, _THIN, progress)
    return _screen(bot, _readiness(held), ReadinessState.RUN_BLOCKED)


def _thin_step_warning() -> BotsView:
    """Nothing blocks Start; one check advises, once under Grids with its button and once in the list."""
    return _screen(
        _bot(BotLifecycleState.DRAFT, _THIN), _readiness(), ReadinessState.READY
    )


def _ready_draft() -> BotsView:
    """Every check passed: a quiet banner and one folded row."""
    return _screen(
        _bot(BotLifecycleState.DRAFT, _FINE), _readiness(), ReadinessState.READY
    )


def _unsaved_design() -> BotsView:
    """`BUG-261`: a new Grid designed in the editor and not saved. The saved config holds no figure,
    yet the Plan group shows the design's capital, step, edges and exits, under "Plan (not saved)"."""
    return _screen(
        _bot(BotLifecycleState.DRAFT, {}),
        _readiness(),
        ReadinessState.READY,
        design=_FINE,
    )


def _running_bot() -> BotsView:
    """A running Futures bot: no readiness, no banner; the figures first, the checks last."""
    progress = BotProgress(
        realised_profit=Decimal("41.20"),
        completed_cycles=9,
        open_orders=4,
        inventory=Decimal("0.308"),
        average_cost=Decimal("2410.5"),
        reason="",
        reason_detail="",
        mark_price=_LAST,
        mark_price_at=_NOW - timedelta(seconds=40),
        pnl=PnlSummary(
            # `BOT-229`: realised (against the average cost) is the grid cycles plus the sells of
            # the opening inventory; the total is realised + unrealised + funding.
            total=Decimal("49.54"),
            realised=Decimal("42.15"),
            unrealised=Decimal("7.7"),
            grid_profit=Decimal("41.20"),
            hodl=None,
            unpriced_fees=0,
            commissions=Decimal("0.8123"),
            funding=Decimal("-0.31"),
        ),
    )
    return _screen(
        _bot(BotLifecycleState.RUNNING, _FINE, progress),
        None,
        ReadinessState.NOT_CONNECTED,
    )


FRAMES: Mapping[str, Callable[[], BotsView]] = {
    "blocked_by_held_position": _blocked_by_held_position,
    "thin_step_warning": _thin_step_warning,
    "ready_draft": _ready_draft,
    "running_bot": _running_bot,
    "unsaved_design": _unsaved_design,
}


def build_frame(name: str, size: tuple[int, int] = _WINDOW) -> QWidget:
    """@raise KeyError `name` is not one of `FRAMES`."""
    view = FRAMES[name]()
    view.resize(*size)
    return view


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One frame of the Bots screen's Plan dock."
    )
    parser.add_argument("frame", choices=sorted(FRAMES))
    parser.add_argument(
        "--png", metavar="PATH", help="Save the frame instead of showing it."
    )
    parser.add_argument("--size", default="1360x1500", metavar="WxH")
    args = parser.parse_args()
    width, height = (int(part) for part in args.size.split("x"))
    app = QApplication.instance() or QApplication(sys.argv)
    widget = build_frame(args.frame, (width, height))
    widget.show()
    if args.png:
        # The rows ask for the height of their wrapped text once the window has its width, and the
        # layout that makes room for it is a second pass.
        for _ in range(3):
            app.processEvents()
        widget.grab().save(args.png)
        return
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
