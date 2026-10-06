"""The report's figures as raw values and one read-out (`EPIC-033N`):
`stat_cards_to_qml` carries a figure and its kind, never its text, and
`cards_readout` turns the cards into the rows `AppValueFormatter` writes."""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.performance_metrics_view import (
    build_primary_stat_cards,
    cards_readout,
    stat_cards_to_qml,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 1, 2, tzinfo=UTC)
_T2 = datetime(2026, 1, 3, tzinfo=UTC)


def _trade(pnl: float) -> Trade:
    return Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T1,
        exit_price=100.0 + pnl,
        quantity=1.0,
        pnl=pnl,
        pnl_percent=pnl,
        fees_paid=0.0,
    )


def _result(trades: list[Trade], equity_curve) -> BacktestResult:
    return BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1000.0 + sum(t.pnl for t in trades),
        trades=trades,
        equity_curve=equity_curve,
        metrics=BacktestMetrics.compute(trades, equity_curve, 1000.0),
    )


def test_max_drawdown_card_is_an_amount_with_its_loss_marked_by_a_minus_percent():
    # Peak 1200 -> trough 1000: a 200 drop, 16.67% of the peak.
    result = _result(
        trades=[_trade(200.0), _trade(-200.0)],
        equity_curve=[(_T0, 1000.0), (_T1, 1200.0), (_T2, 1000.0)],
    )

    drawdown = next(
        c for c in build_primary_stat_cards(result) if c.title == "Max Drawdown"
    )

    assert drawdown.value == "200.00"
    assert drawdown.badge_text == "-16.67%"
    assert drawdown.badge_tone is Tone.NEGATIVE


def test_stat_cards_to_qml_carries_raw_figures_and_their_kind_not_text():
    result = _result(trades=[_trade(50.0)], equity_curve=[(_T0, 1000.0), (_T1, 1050.0)])

    qml_cards = stat_cards_to_qml(build_primary_stat_cards(result))

    assert all(
        set(card.keys())
        == {
            "key",
            "title",
            "figure",
            "kind",
            "valueTone",
            "suffix",
            "badgeTitle",
            "badgeFigure",
            "badgeKind",
            "badgeTone",
        }
        for card in qml_cards
    )
    net_pnl = next(card for card in qml_cards if card["title"] == "Net PnL")
    assert net_pnl["figure"] == 50.0
    assert net_pnl["kind"] is ColumnKind.MONEY
    assert net_pnl["badgeFigure"] == 5.0
    assert net_pnl["badgeKind"] is ColumnKind.PERCENT


def test_cards_become_one_readout_with_a_row_per_figure_and_badge():
    result = _result(
        trades=[_trade(50.0), _trade(-10.0)],
        equity_curve=[(_T0, 1000.0), (_T1, 1050.0), (_T2, 1040.0)],
    )

    readout = cards_readout(stat_cards_to_qml(build_primary_stat_cards(result)))

    assert [(spec.key, spec.title, spec.kind) for spec in readout.specs] == [
        ("net_pnl", "Net PnL (USD)", ColumnKind.MONEY),
        ("net_pnl.badge", "Net PnL (%)", ColumnKind.PERCENT),
        ("max_drawdown", "Max Drawdown (USD)", ColumnKind.MONEY),
        ("max_drawdown.badge", "Max Drawdown (%)", ColumnKind.PERCENT),
        ("win_rate", "Win Rate", ColumnKind.PERCENT),
        ("win_rate.badge", "Winning / closed trades", ColumnKind.TEXT),
        ("profit_factor.ratio", "Profit Factor", ColumnKind.QUANTITY),
    ]
    assert readout.values["net_pnl"] == 40.0
    assert readout.values["win_rate.badge"] == "1 / 2"
    # No verdict to give, so no row for it.
    assert "profit_factor.ratio.badge" not in readout.values


def test_a_losing_profit_factor_gets_its_verdict_as_a_row():
    result = _result(
        trades=[_trade(-50.0), _trade(-10.0)],
        equity_curve=[(_T0, 1000.0), (_T1, 950.0), (_T2, 940.0)],
    )

    readout = cards_readout(stat_cards_to_qml(build_primary_stat_cards(result)))

    assert readout.values["profit_factor.ratio.badge"] == "Risk"
