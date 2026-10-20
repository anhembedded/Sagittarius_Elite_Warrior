"""`BOT-206` — the Plan panel writes its figures and its readiness into the property table, and
keeps the blocking reason as text above it.

The words are the screen's own (`bot_facts`, `bot_ladder_facts`, `readiness_words`), so a test reads
what the table shows and compares it with what those functions say. The conformance helpers are
the suite's own: the table must pass the checks every item view of the workbench passes.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import QStyleOptionViewItem
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
    GridLadder,
    RecordedCycles,
    grid_ladder_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_pnl import PnlSummary
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    bot_facts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_plan_panel import (
    BotPlanPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_property_grid import (
    VALUE_COLUMN,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_property_rows import (
    READINESS_GROUP,
    step_key,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.notice_bar import NoticeKind
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_column_checks import (
    alignment_problems,
    digit_font_problems,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_widget_checks import (
    item_view_problems,
)

from .bots_screen_fixtures import NOW, stored

_COSTS = PnlSummary(
    total=Decimal("9.5"),
    realised=Decimal(12),
    unrealised=Decimal("0.5"),
    grid_profit=Decimal(12),
    hodl=None,
    unpriced_fees=0,
    commissions=Decimal("0.0042"),
    funding=Decimal("-0.0317"),
)
_PROGRESS = BotProgress(
    realised_profit=Decimal("12.5"),
    completed_cycles=3,
    open_orders=2,
    inventory=Decimal("0.01"),
    average_cost=Decimal(64000),
    reason="",
    reason_detail="",
    pnl=_COSTS,
)


def _bot(
    venue: TradingVenue,
    state: BotLifecycleState = BotLifecycleState.HALTED,
    progress: BotProgress | None = _PROGRESS,
) -> BotSnapshot:
    """A bot of `state` on `venue` with a run's figures."""
    bot = BotSnapshot.of(stored("a00001", state).bot, progress)
    return replace(bot, venue=venue)


_BLOCKER = ReadinessItem(
    ReadinessStep.DESIGN,
    "CAPITAL_ABOVE_BALANCE",
    "The capital is 1000 USDT, above the 800.00 USDT available",
    ReadinessFix.EDIT_FIELD,
    BotRefusal.PARAMETERS_REFUSED,
    "CAPITAL_ABOVE_BALANCE",
)


def _readiness(*items: ReadinessItem) -> BotReadiness:
    """Connect done; Design open with the given items, or done; Run after it."""
    design = tuple(item for item in items if item.step is ReadinessStep.DESIGN)
    return BotReadiness(
        (
            StepReadiness(ReadinessStep.CONNECT, StepStatus.DONE),
            StepReadiness(
                ReadinessStep.DESIGN,
                StepStatus.OPEN if design else StepStatus.DONE,
                design,
            ),
            StepReadiness(
                ReadinessStep.RUN,
                StepStatus.WAITING if design else StepStatus.DONE,
            ),
        )
    )


def _panel(qtbot, venue: TradingVenue = TradingVenue.FUTURES_TESTNET) -> BotPlanPanel:
    model = BotsViewModel()
    panel = BotPlanPanel(model)
    qtbot.addWidget(panel)
    bot = _bot(venue)
    model.set_selected(bot)
    model.set_facts(bot_facts(bot, NOW))
    panel.resize(520, 900)
    panel.show()
    return panel


def test_the_values_are_what_bot_facts_says_through_the_applications_formatter(
    qtbot,
) -> None:
    panel = _panel(qtbot)
    facts = bot_facts(_bot(TradingVenue.FUTURES_TESTNET), NOW)

    figures = panel.properties
    assert figures.shown_value("total_pnl") == facts.total_pnl
    assert figures.shown_value("grid_profit") == facts.grid_profit
    assert figures.shown_value("commissions") == facts.commissions == "0.0042"
    assert figures.shown_value("funding") == "-0.0317"
    assert figures.shown_value("inventory") == facts.inventory


def test_the_running_time_is_a_duration_the_formatter_writes(qtbot) -> None:
    panel = _panel(qtbot)
    running = replace(
        _bot(TradingVenue.SPOT_TESTNET, BotLifecycleState.RUNNING),
        run_started_at=NOW - timedelta(hours=1, minutes=5),
    )

    panel._model.set_selected(running)
    panel._model.set_facts(bot_facts(running, NOW))

    assert panel.properties.shown_value("running_time") == "1:05:00"


def test_the_table_passes_the_workbench_checks_every_item_view_passes(qtbot) -> None:
    panel = _panel(qtbot)
    window = panel.window()

    assert item_view_problems(window, panel) == []
    assert alignment_problems(window, panel) == []
    assert digit_font_problems(window, panel) == []


def test_a_collapsed_group_stays_collapsed_while_the_figures_refresh(qtbot) -> None:
    panel = _panel(qtbot)
    view = panel.properties.view
    results = panel.properties._group_index("results")
    view.collapse(results)

    panel.properties.set_values({"grid_profit": "99.00"})
    panel._model.set_facts(bot_facts(_bot(TradingVenue.FUTURES_TESTNET), NOW))

    assert not view.isExpanded(results)
    assert view.isExpanded(panel.properties._group_index("plan"))


def test_a_spot_bot_has_no_cost_or_liquidation_rows_and_a_futures_bot_has(
    qtbot,
) -> None:
    spot = _panel(qtbot, TradingVenue.SPOT_TESTNET)
    futures = _panel(qtbot)

    assert not spot.properties.row_is_shown("commissions")
    assert not spot.properties.row_is_shown("funding")
    assert futures.properties.row_is_shown("commissions")
    assert futures.properties.row_is_shown("funding")
    assert spot.properties.row_is_shown("grid_profit")


def test_the_readiness_group_is_the_bot_at_rests_alone(qtbot) -> None:
    panel = _panel(qtbot)
    model = panel._model

    model.set_readiness(_readiness(_BLOCKER), ReadinessState.DESIGNING)
    assert panel.properties.group_is_shown(READINESS_GROUP)
    assert (
        panel.properties.shown_value(step_key(ReadinessStep.DESIGN)) == "1 thing left"
    )

    model.set_readiness(None, ReadinessState.NOT_CONNECTED)
    assert not panel.properties.group_is_shown(READINESS_GROUP)


def test_the_blocking_reason_is_the_banner_above_the_table_with_a_sign_and_in_no_cell(
    qtbot,
) -> None:
    panel = _panel(qtbot)
    panel._model.set_selected(
        _bot(TradingVenue.SPOT_TESTNET, BotLifecycleState.DRAFT, None)
    )
    panel._model.set_readiness(_readiness(_BLOCKER), ReadinessState.DESIGNING)

    banner = panel.banner
    table = panel.properties.view

    assert _BLOCKER.reason in banner.text
    assert banner.isVisible() and banner.kind is NoticeKind.CRITICAL
    assert (
        banner.mapTo(panel, banner.rect().topLeft()).y()
        < table.mapTo(panel, table.rect().topLeft()).y()
    )
    cells = [
        panel.properties.shown_value(key) + panel.properties.shown_title(key)
        for key in panel.properties.row_keys()
    ]
    assert not any("1000 USDT" in cell for cell in cells)


def test_nothing_blocking_start_means_no_sign(qtbot) -> None:
    panel = _panel(qtbot)
    panel._model.set_readiness(_readiness(_BLOCKER), ReadinessState.DESIGNING)
    assert panel.banner.kind is NoticeKind.CRITICAL

    panel._model.set_readiness(_readiness(), ReadinessState.READY)

    assert panel.banner.kind is NoticeKind.INFORMATION
    assert panel.banner.text == "Ready to start"


def test_a_bot_with_a_run_keeps_its_figures_and_no_readiness(qtbot) -> None:
    panel = _panel(qtbot)
    panel._model.set_selected(
        _bot(TradingVenue.SPOT_TESTNET, BotLifecycleState.RUNNING)
    )
    panel._model.set_readiness(None, ReadinessState.NOT_CONNECTED)

    assert not panel.properties.group_is_shown(READINESS_GROUP)
    assert panel.properties.group_is_shown("results")


def _value_colour(panel: BotPlanPanel, key: str):
    grid = panel.properties
    option = QStyleOptionViewItem()
    grid.view.itemDelegate().initStyleOption(
        option, grid._proxy_index(key, VALUE_COLUMN)
    )
    return option.palette.color(QPalette.ColorRole.Text)


def test_the_panel_paints_each_earnings_figure_by_what_it_means(qtbot) -> None:
    """`EPIC-043C`: a run that is ahead reads in the profit colour, one that is behind in the loss
    colour, and the same rows return to the platform's colour with no verdict."""
    panel = _panel(qtbot)
    palette = QGuiApplication.palette()
    assert _value_colour(panel, "total_pnl") == tone_colour(Tone.POSITIVE, palette)
    assert _value_colour(panel, "grid_profit") == tone_colour(Tone.POSITIVE, palette)

    behind = _bot(
        TradingVenue.FUTURES_TESTNET,
        progress=replace(
            _PROGRESS, pnl=replace(_COSTS, total=Decimal(-3), hodl=Decimal(-1))
        ),
    )
    panel._model.set_selected(behind)
    panel._model.set_facts(bot_facts(behind, NOW))

    assert _value_colour(panel, "total_pnl") == tone_colour(Tone.NEGATIVE, palette)
    assert _value_colour(panel, "hodl") == tone_colour(Tone.NEGATIVE, palette)
    assert panel.properties.shown_value("total_pnl").startswith("▼ -3.00")
    assert _value_colour(panel, "symbol") != _value_colour(panel, "total_pnl")


def test_the_panel_paints_the_ladders_cycle_average_by_what_it_means(qtbot) -> None:
    """`EPIC-043C`: the ladder rows reach the grid with their tones, as the earnings do; a cycle
    that earned reads in the profit colour, one that lost in the loss colour."""
    panel = _panel(qtbot)
    palette = QGuiApplication.palette()
    ladder = grid_ladder_of(_bot(TradingVenue.FUTURES_TESTNET), NOW)
    assert isinstance(ladder, GridLadder)

    for booked, tone in ((Decimal(10), Tone.POSITIVE), (Decimal(-10), Tone.NEGATIVE)):
        recorded = RecordedCycles(completed_cycles=2, grid_profit=booked)
        panel._model.set_ladder(replace(ladder, recorded=recorded))
        assert _value_colour(panel, "cycle_average") == tone_colour(tone, palette)
    assert panel.properties.shown_value("cycle_average").startswith("▼ -5.00")
