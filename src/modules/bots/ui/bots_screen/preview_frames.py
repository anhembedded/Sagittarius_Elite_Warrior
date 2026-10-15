"""`EPIC-039J` — the Bots screen on a Futures venue, one frame per state worth looking at.

Offline, like `preview.py`: the screen is filled directly and the verdicts are the real
planner's (`evaluate_grid` over sample numbers), so every sentence on a frame is the one a
user would read. `build_preview()` in `preview.py` stays the Spot screen; these frames are the
owner's visual check of what a Futures bot adds (`ui-presentation-rule.md` §5):

  futures_long_plan · futures_short_plan · futures_neutral_plan · futures_refused_plan ·
  futures_liquidation_warning · futures_drift_halt

Run one with `python -m Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.preview_frames
<frame> [--png path]` (offscreen with `--png`, a window otherwise).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from PySide6.QtWidgets import QApplication, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotProgress,
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
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    bot_facts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_plan_judge import (
    verdict_line,
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

_NOW = datetime(2026, 10, 13, 12, tzinfo=UTC)
_VENUE = TradingVenue.FUTURES_TESTNET


def _profile_of_the_venue() -> VenueProfile:
    profile = venue_profile_of(_VENUE)
    if profile is None:
        raise LookupError(f"{_VENUE.display_name} has no venue profile to preview")
    return profile


_PROFILE = _profile_of_the_venue()
_SYMBOL = "BTCUSDT"
_LAST = Decimal(65000)
_RANGE = {
    "lower": "60000",
    "upper": "70000",
    "grid_count": "10",
    "spacing": "ARITHMETIC",
}
_TERMS = ExchangeTerms(
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.00001"),
    min_notional=Decimal(5),
    maker_fee=Decimal("0.0002"),
    taker_fee=Decimal("0.0005"),
    max_notional_per_order=Decimal(50000),
    max_open_orders=100,
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


def _config(direction: str, leverage: int, **changes: str) -> dict[str, str]:
    base = {
        **_RANGE,
        "capital_quote": "10000",
        "stop_loss": "percent:5",
        "take_profit": "percent:5",
        "direction": direction,
        "leverage": str(leverage),
    }
    return {**base, **changes}


def _verdicts(config: dict[str, str], atr: Decimal) -> tuple[Verdict, ...]:
    """What the planner says about `config`, with the facts a Futures testnet gives."""
    facts = PlanRiskFacts(
        FuturesSymbolSetting(
            _SYMBOL, int(config["leverage"]), MarginType.ISOLATED, Decimal(10**9)
        ),
        _BRACKETS,
    )
    limits = ExposureLimits(_PROFILE.directions, _PROFILE.max_leverage)
    inputs = BotKindInputs(
        config,
        _TERMS,
        MarketView(_LAST, atr, base_asset="BTC", quote_asset="USDT"),
        None,
        limits,
        facts,
    )
    return evaluate_grid(inputs, GridThresholds()).verdicts


def _bot(
    state: BotLifecycleState, config: dict[str, str], progress: BotProgress | None
) -> BotSnapshot:
    return BotSnapshot(
        bot_id="f00001",
        name=f"BTC futures grid {state.value.lower()}",
        kind="grid",
        venue=_VENUE,
        symbol=_SYMBOL,
        state=state,
        created_at=_NOW - timedelta(days=2),
        run_started_at=None if progress is None else _NOW - timedelta(hours=30),
        config=config,
        progress=progress,
    )


def _screen(bot: BotSnapshot, verdicts: tuple[Verdict, ...]) -> BotsView:
    view = BotsView()
    view.model.set_bots((bot,))
    view.model.set_selected(bot)
    view.model.set_facts(bot_facts(bot, _NOW))
    view.model.set_judgement(tuple(verdict_line(verdict) for verdict in verdicts))
    view.model.set_availability(
        {
            action: availability(bot.state, action, StartConditions())
            for action in BotAction
        }
    )
    panel = GridPanel()
    panel.set_profile(_PROFILE)
    panel.set_config(bot.config)
    panel.show_verdicts(verdicts)
    view.set_kind_panel(panel)
    view.apply_ui_mode(
        BotsUiState.EDITING_DRAFT
        if bot.state is BotLifecycleState.DRAFT
        else BotsUiState.VIEWING
    )
    view.resize(1200, 820)
    return view


def _plan(direction: str, **changes: str) -> BotsView:
    config = _config(direction, 3, **changes)
    return _screen(
        _bot(BotLifecycleState.DRAFT, config, None), _verdicts(config, Decimal(2500))
    )


def _refused() -> BotsView:
    config = _config("LONG", 25, stop_loss="off")
    return _screen(
        _bot(BotLifecycleState.DRAFT, config, None), _verdicts(config, Decimal(2500))
    )


def _liquidation_warning() -> BotsView:
    config = _config("LONG", 8, stop_loss="percent:1")
    return _screen(
        _bot(BotLifecycleState.DRAFT, config, None), _verdicts(config, Decimal(9000))
    )


def _drift_halt() -> BotsView:
    config = _config("LONG", 3)
    pnl = PnlSummary(
        total=Decimal("37.4"),
        realised=Decimal("41.2"),
        unrealised=Decimal("-1.1"),
        grid_profit=Decimal("41.2"),
        hodl=None,
        unpriced_fees=0,
        commissions=Decimal("1.3726"),
        funding=Decimal("-2.7000"),
    )
    progress = BotProgress(
        realised_profit=Decimal("41.2"),
        completed_cycles=9,
        open_orders=0,
        inventory=Decimal("0.0615"),
        average_cost=Decimal(63100),
        reason="settings_drift",
        reason_detail=(
            "BTCUSDT leverage on the exchange is 5x; the bot asked for 3x and does not "
            "change it. Its position stands and its orders are cancelled."
        ),
        mark_price=Decimal(62800),
        pnl=pnl,
    )
    bot = _bot(BotLifecycleState.HALTED, config, progress)
    return _screen(bot, _verdicts(config, Decimal(2500)))


FRAMES: Mapping[str, Callable[[], BotsView]] = {
    "futures_long_plan": lambda: _plan("LONG"),
    "futures_short_plan": lambda: _plan("SHORT"),
    "futures_neutral_plan": lambda: _plan("NEUTRAL"),
    "futures_refused_plan": _refused,
    "futures_liquidation_warning": _liquidation_warning,
    "futures_drift_halt": _drift_halt,
}


def build_frame(name: str) -> QWidget:
    """@raise KeyError `name` is not one of `FRAMES`."""
    return FRAMES[name]()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One Futures frame of the Bots screen."
    )
    parser.add_argument("frame", choices=sorted(FRAMES))
    parser.add_argument(
        "--png", metavar="PATH", help="Save the frame instead of showing it."
    )
    args = parser.parse_args()
    app = QApplication.instance() or QApplication(sys.argv)
    widget = build_frame(args.frame)
    if args.png:
        widget.grab().save(args.png)
        return
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
