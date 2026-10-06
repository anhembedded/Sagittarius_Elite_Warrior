from __future__ import annotations

from datetime import UTC, datetime, timedelta

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exchange_filters import (
    ExchangeFilters,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_limitations_view import (
    build_backtest_limitations,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.performance_charts import (
    build_drawdown_chart_points,
    build_yearly_returns_rows,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.performance_metrics_view import (
    StatCardData,
    build_result_warning_text,
    stat_cards_to_qml,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.trade_log_row import (
    build_trade_log_rows,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import ratio_key
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

#: This file's parent directory is `ui`, same as every other module's own
#: `preview.py` — the fallback key `scripts/preview_qml.py::discover_previews()`
#: derives from the parent directory name would collide with theirs. Same fix
#: `modules/market_data/ui/preview.py` needed at PR 4.4b.
PREVIEW_KEY = "backtest"


def build_preview() -> QWidget:
    """Builds a standalone preview for the Backtest screen."""
    view = BackTestView()
    view_model = BackTestViewModel()
    view_model.strategyName = "EmaCrossoverStrategy"
    view_model.run_result.set_stat_cards(
        stat_cards_to_qml(
            [
                StatCardData(
                    "net_pnl",
                    "Net PnL",
                    1420.50,
                    ColumnKind.MONEY,
                    Tone.POSITIVE,
                    "USD",
                    "Net PnL (%)",
                    14.21,
                    ColumnKind.PERCENT,
                    Tone.POSITIVE,
                ),
                StatCardData(
                    "max_drawdown",
                    "Max Drawdown",
                    345.0,
                    ColumnKind.MONEY,
                    Tone.NEGATIVE,
                    "USD",
                    "Max Drawdown (%)",
                    -3.45,
                    ColumnKind.PERCENT,
                    Tone.NEGATIVE,
                ),
                StatCardData(
                    "win_rate",
                    "Win Rate",
                    62.5,
                    ColumnKind.PERCENT,
                    Tone.POSITIVE,
                ),
                StatCardData(
                    ratio_key("profit_factor"),
                    "Profit Factor",
                    1.84,
                    ColumnKind.QUANTITY,
                    Tone.POSITIVE,
                ),
            ]
        ),
        [],
    )
    sample_trades = [
        Trade(
            symbol="ETHUSDT",
            entry_time=datetime(2024, 1, 2, 4, 0, tzinfo=UTC),
            entry_price=2250.0,
            exit_time=datetime(2024, 1, 2, 12, 0, tzinfo=UTC),
            exit_price=2310.0,
            quantity=1.0,
            pnl=60.0,
            pnl_percent=2.67,
            fees_paid=4.56,
            entry_reason="EMA Fast > Slow Cross",
            mae_percent=-1.85,
            mfe_percent=3.42,
        )
    ]
    view_model.trade_log.set_rows(build_trade_log_rows(sample_trades))

    # BOT-106D — a synthetic year-long equity curve (peak, drawdown, partial
    # recovery) so the drawdown chart and returns heatmap have something to
    # render standalone, without running a real backtest.
    start = datetime(2024, 1, 1, tzinfo=UTC)
    sample_equity_curve = [
        (start, 10_000.0),
        (start + timedelta(days=45), 11_500.0),
        (start + timedelta(days=90), 9_800.0),
        (start + timedelta(days=150), 10_600.0),
        (start + timedelta(days=220), 12_400.0),
        (start + timedelta(days=300), 11_900.0),
        (start + timedelta(days=364), 13_050.0),
    ]
    # EPIC-027D — the preview shows a Spot run, the market whose screen
    # differs from the default: leverage hidden, no short filters, and the
    # result naming the shorts it ignored and the exchange filters it applied.
    view_model.broker_sim.market = MarketType.SPOT.value
    sample_result = BacktestResult.compute(
        symbol="ETHUSDT",
        initial_balance=10_000.0,
        final_balance=sample_equity_curve[-1][1],
        trades=sample_trades,
        equity_curve=sample_equity_curve,
        ignored_short_signals=3,
        exchange_filters=ExchangeFilters(
            step_size=0.0001, min_quantity=0.0001, min_notional=5.0, tick_size=0.01
        ),
        market_type=MarketType.SPOT,
    )
    view_model.run_result.set_limitations(build_backtest_limitations(sample_result))
    view_model.run_result.set_result_warning_text(
        build_result_warning_text(sample_result)
    )
    view_model.run_result.set_drawdown_points(
        build_drawdown_chart_points(sample_result)
    )
    view_model.run_result.set_yearly_returns(build_yearly_returns_rows(sample_result))

    view.set_view_model(view_model)
    # EPIC-027D — builds the chart card so `chart_controls` exists and
    # `_show_marker_sides()` actually runs once, the same call order
    # `BackTestPresenter` uses (`render_symbol_cards` after the view model),
    # so the preview's Spot run really demonstrates "Short only" dropped
    # from the chart's side filter, not just the trade-log tab.
    view.render_symbol_cards(["ETHUSDT"])
    view.resize(1400, 850)
    return view
