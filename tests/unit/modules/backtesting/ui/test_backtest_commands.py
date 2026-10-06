"""`EPIC-033D` — the Backtest mode's commands are actions.

The commands the backtesting module really contributes, bound by
`bind_backtest_commands` over a real `BackTestViewModel`. These replace the
top panel's Run/Cancel and report buttons (`BOT-115B`-`D`, `BOT-107A`-`B`):
the same requests, now from the Backtest menu and toolbar.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from PySide6.QtGui import QKeySequence
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_command_binding import (
    bind_backtest_commands,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_commands import (
    COMPARE_REPORTS,
    EXPORT_TRADES,
    IMPORT_REPORT,
    MONTE_CARLO,
    OUT_OF_SAMPLE,
    RUN,
    SAVE_REPORT,
    STOP,
    backtest_commands,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_screen import (
    BACKTEST_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.trade_log_row import (
    TradeLogRow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Tone
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.conftest import real_contributions

_REQUESTS = {
    RUN: "runBacktestRequested",
    IMPORT_REPORT: "importReportRequested",
    COMPARE_REPORTS: "openCompareReportsRequested",
    OUT_OF_SAMPLE: "openOutOfSampleComparisonRequested",
    MONTE_CARLO: "openMonteCarloRequested",
}


def _actions(view_model: BackTestViewModel):
    return bound_actions(
        view_model,
        backtest_commands(BACKTEST_ROUTE),
        lambda binder: bind_backtest_commands(binder, view_model, None),
    )


def _show_a_result(view_model: BackTestViewModel) -> None:
    view_model.run_result.set_stat_cards(
        primary=[
            {
                "title": "WIN RATE",
                "value": "10.33%",
                "valueTone": Tone.NEUTRAL,
                "suffix": "",
                "badgeText": "92/891 trades",
                "badgeTone": Tone.NEUTRAL,
            }
        ],
        extended=[],
    )


def test_the_backtesting_module_contributes_every_backtest_command() -> None:
    modes = {
        command.command_id: command.mode
        for command in real_contributions(Mock()).commands()
    }

    for command_id in (*_REQUESTS, STOP, SAVE_REPORT, EXPORT_TRADES):
        assert modes[command_id] == BACKTEST_ROUTE


@pytest.mark.parametrize(("command_id", "signal_name"), _REQUESTS.items())
def test_each_idle_action_makes_its_request(qapp, command_id, signal_name) -> None:
    view_model = BackTestViewModel()
    actions = _actions(view_model)
    heard: list[bool] = []
    getattr(view_model, signal_name).connect(lambda *_args: heard.append(True))

    actions.action(command_id).trigger()

    assert heard == [True]


def test_run_is_f7_and_stop_applies_only_while_a_run_or_sync_is_going(qapp) -> None:
    view_model = BackTestViewModel()
    actions = _actions(view_model)
    run, stop = actions.action(RUN), actions.action(STOP)
    stopped: list[bool] = []
    view_model.cancelBacktestRequested.connect(lambda: stopped.append(True))
    assert run.shortcut() == QKeySequence("F7")
    assert run.isEnabled() and not stop.isEnabled()

    view_model.set_ui_mode("RUNNING")
    assert stop.isEnabled() and not run.isEnabled()
    stop.trigger()
    assert stopped == [True]

    view_model.set_ui_mode("CANCELLING")
    assert not stop.isEnabled() and not run.isEnabled()


def test_save_report_applies_once_a_result_exists(qapp) -> None:
    view_model = BackTestViewModel()
    actions = _actions(view_model)
    save = actions.action(SAVE_REPORT)
    saved: list[bool] = []
    view_model.exportReportRequested.connect(lambda: saved.append(True))
    assert not save.isEnabled()

    _show_a_result(view_model)
    save.trigger()

    assert save.isEnabled()
    assert saved == [True]


def test_export_trades_applies_while_trades_are_listed(qapp) -> None:
    """`EPIC-033L`: the Trades panel's Export button is Tools → Export
    trades…, which writes the trades the panel lists."""
    view_model = BackTestViewModel()
    actions = _actions(view_model)
    export = actions.action(EXPORT_TRADES)
    asked: list[bool] = []
    view_model.trade_log.exportRequested.connect(lambda: asked.append(True))
    assert not export.isEnabled()
    moment = datetime(2026, 1, 1, tzinfo=UTC)

    view_model.trade_log.set_rows(
        [TradeLogRow(1, moment, 1.0, moment, 1.0, 1.0, 0.0, 0.0)]
    )
    export.trigger()

    assert asked == [True]
    view_model.trade_log.set_rows([])
    assert not export.isEnabled()
