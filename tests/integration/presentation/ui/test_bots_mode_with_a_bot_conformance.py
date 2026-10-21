"""`EPIC-040` F2 — the Bots mode with a backtestable bot selected passes every check of the
conformance suite, on each centre tab, at each window size; and each is pictured for a reviewer
(`pr-review` SKILL §5.1).

The conformance suite boots the app with no bot, so the Bots mode it measures has no chart and no
workbench page: the Backtest tab's setup column, result tabs and interval row were in no check, and
the missing "More timeframes…" menu command (F1) went unseen. Here the app runs as in
`test_trade_mode_conformance.py` (Spot Testnet against the fake Binance server), a Grid bot is
created through the application's own command, selected as a click would, and both tabs of the
centre are measured. Known failures only shrink, as the suite's do: they are
`baseline_workbench_conformance.json`'s `failing_with_a_bot`, keyed `bots~live` and `bots~backtest`,
and ratcheted by the suite's own `ratchet_problems`.

**What it measures.** The checks of the item: the menus (access keys, separators, mnemonics), the
toolbars (actions only, each in a menu, reading as its menu item, no button repeating a command),
the scroll areas, the tables' columns and the combo boxes' text (`BUG-245`: with a bot selected the
Bots table, the Ladder and the venue combo ran past their edges; the Ladder is measured with its
tab in front, a tab behind another is not drawn), and the size. Known failures only shrink, as the
suite's do. The wrapped text of the Plan column and the Backtest setup column (`BUG-246`) is read
by `wrapped_text_problems`.

Retire when: the conformance suite's own boot creates a bot.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_presenter import (
    BotsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.tests.integration.modules.bots.grid_fake_exchange import (
    GRID,
    SYMBOL,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.test_workbench_conformance import (
    BASELINE_FILE,
    MODE_CHECKS,
    WINDOW_SIZES,
    ratchet_problems,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.trade_mode_boot import (
    SPOT,
    Boot,
    TradeDesk,
    trade_mode_running,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_layout_checks import (
    fit_problems,
    wrapped_text_problems,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_screenshots import (
    SCREENSHOT_DIR_ENV,
    apply_scheme,
    is_blank,
    restore_scheme,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_widget_checks import (
    plain_text,
    top_menus,
)

_WAIT_MS = 15_000
_MIDDLE_LIGHTNESS = 128
#: The picker dialog's pin column.
_PIN_COLUMN = 2
#: The checks of `MODE_CHECKS` this case measures (`EPIC-040` F2, `BUG-245`): menus, toolbars, scroll areas, columns and combos.
_MEASURED = (
    "access_keys_unique",
    "menu_separators_between_groups",
    "mnemonics_escaped",
    "toolbar_actions_only",
    "toolbar_actions_in_a_menu",
    "toolbar_text_matches_menu",
    "no_button_duplicates_a_command",
    "no_nested_scroll",
    "columns_shown_whole",
    "combo_text_shown_whole",
)


def _baseline() -> dict[str, list[str]]:
    data = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    baseline: dict[str, list[str]] = data["failing_with_a_bot"]
    return baseline


@pytest.fixture
def boot(request: pytest.FixtureRequest) -> Boot:
    return Boot.from_request(request)


def _settle() -> None:
    for _ in range(3):
        QApplication.processEvents()


def _own_data_root(boot: Boot) -> None:
    """The bot this case creates is kept in this test's own data root, never the session's: a bot
    that outlived its test would be in the next test's window, and in every other app-booting
    test on the same worker (`testing-rule.md`: tests do not share state)."""
    root = boot.tmp_path / "data_root"
    root.mkdir()
    boot.monkeypatch.setenv(DATA_ROOT_ENV, str(root))


def _select_a_grid_bot(desk: TradeDesk, boot: Boot) -> BotsPresenter:
    """The Bots mode in front, a Grid bot made through the application's command and selected as
    a click on its row would, until the Backtest tab has the workbench page."""
    desk.window.switch_screen(BOTS_ROUTE)
    presenter = desk.window.presenters[BOTS_ROUTE]
    assert isinstance(presenter, BotsPresenter)
    created = desk.container.resolve(ICommandDispatcher).dispatch(
        CreateBotCommand, CreateBotCommand("grid", "grid", SPOT, SYMBOL, GRID)
    )
    assert isinstance(created, BotCommandResult) and created.bot_id is not None
    view = presenter.view
    model = view.model
    boot.qtbot.waitUntil(
        lambda: any(bot.bot_id == created.bot_id for bot in model.bots),
        timeout=_WAIT_MS,
    )
    model.select_requested.emit(created.bot_id)
    boot.qtbot.waitUntil(
        lambda: (
            isinstance(view.shown_backtest_page(), BacktestWorkbenchView)
            and view.backtest_enabled
        ),
        timeout=_WAIT_MS,
    )
    _settle()
    return presenter


def _save_dark(window: QMainWindow, path: Path) -> None:
    """The same tab in the dark scheme, for the owner to judge beside the light one."""
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    apply_scheme(app, "dark")
    try:
        _settle()
        assert window.palette().window().color().lightness() < _MIDDLE_LIGHTNESS
        assert window.grab().save(str(path)), path
    finally:
        restore_scheme(app)
        _settle()


def _tabs(presenter: BotsPresenter) -> dict[str, Callable[[], None]]:
    view = presenter.view
    return {"live": view.show_live, "backtest": view.show_backtest}


@pytest.mark.parametrize(
    "size", [QSize(*s) for s in WINDOW_SIZES], ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_the_bots_mode_conforms_with_a_bot_selected_on_each_tab(
    boot: Boot, size: QSize, tmp_path: Path
) -> None:
    out_dir = Path(os.environ.get(SCREENSHOT_DIR_ENV) or tmp_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    label = f"{size.width()}x{size.height()}"
    report: dict[str, dict[str, list[str]]] = {}
    _own_data_root(boot)
    with trade_mode_running(boot) as desk:
        window = desk.window
        presenter = _select_a_grid_bot(desk, boot)
        window.resize(size)
        _settle()
        host = window.hosts[BOTS_ROUTE]
        for tab, show in _tabs(presenter).items():
            show()
            _settle()
            # Pictured as the person sees the tab, before the checks rearrange the layout.
            path = out_dir / f"{BOTS_ROUTE}~{tab}-with-a-bot@{label}.png"
            assert window.grab().save(str(path)), path
            _save_dark(window, path.with_name(path.name.replace("@", "~dark@")))
            assert not QImage(str(path)).isNull()
            assert not is_blank(host.centralWidget().grab().toImage()), tab
            checks = {name: MODE_CHECKS[name](window, host) for name in _MEASURED}
            if tab == "live":
                # The Ladder is tabbed behind Orders: it is measured with its tab in front.
                presenter.view.show_ladder()
                _settle()
                checks["columns_shown_whole"] += MODE_CHECKS["columns_shown_whole"](
                    window, host
                )
            checks["fits_the_window"] = fit_problems(window, host, size)
            view = presenter.view
            plan = view.plan if tab == "live" else view.shown_backtest_page()
            assert plan is not None
            # The Plan is the Live tab's own: the Backtest tab shows none of it (`BOT-218`).
            assert view.plan.isVisibleTo(view.centre) == (tab == "live")
            checks["wrapped_text_shown_whole"] = wrapped_text_problems(window, plan)
            report[f"{BOTS_ROUTE}~{tab}"] = checks

    problems = ratchet_problems(_baseline(), report, size)
    assert not problems, "\n".join(problems)


def _save_chart_menu(desk: TradeDesk, path: Path) -> bool:
    """Saves View → Chart, filled for the showing mode as opening it would, and says whether its
    More timeframes… is live. Read and drawn in one place: the window builds the submenu inside the
    View menu and takes it away again when it fills that menu next."""
    view_menu = dict(top_menus(desk.window))["View"]
    submenus = [
        item for item in view_menu.actions() if plain_text(item.text()) == "Chart"
    ]
    assert len(submenus) == 1, "View has no single Chart submenu in the Bots mode"
    chart = submenus[0].menu()
    assert chart is not None
    more = [a for a in chart.actions() if plain_text(a.text()) == "More timeframes…"]
    assert len(more) == 1
    assert chart.grab().save(str(path)), path
    return more[0].isEnabled()


def test_the_chart_menu_and_the_pickers_refusal_are_pictured(
    boot: Boot, tmp_path: Path
) -> None:
    """`EPIC-040` F1 and F4 as the person meets them: View → Chart in front of each tab, with
    More timeframes… live, and the interval picker's dialog after the last pin was unticked."""
    out_dir = Path(os.environ.get(SCREENSHOT_DIR_ENV) or tmp_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    _own_data_root(boot)
    with trade_mode_running(boot) as desk:
        window = desk.window
        presenter = _select_a_grid_bot(desk, boot)
        window.resize(QSize(1366, 768))
        _settle()
        for tab, show in _tabs(presenter).items():
            show()
            _settle()
            path = out_dir / f"{BOTS_ROUTE}~view-chart-menu-on-{tab}@1366x768.png"
            assert _save_chart_menu(desk, path), tab
            assert not is_blank(QImage(str(path))), tab

        page = presenter.view.shown_backtest_page()
        assert isinstance(page, BacktestWorkbenchView)
        toolbar = page.interval
        toolbar.timeframes.more_action.trigger()
        picker = toolbar._picker
        assert picker is not None and picker.isVisible()
        # The person unticks every pin, one after the other, as the dialog lets them: the one Run
        # replays stays, and the dialog says why.
        chosen = page.chosen_interval().value
        pinned = [row.code for row in toolbar._selection.pinned_rows]
        for code in sorted(pinned, key=lambda code: code == chosen):
            item = picker.item_for(code)
            assert item is not None
            item.setCheckState(_PIN_COLUMN, Qt.CheckState.Unchecked)
        _settle()
        assert [a.text() for a in toolbar.timeframes.timeframe_actions()] == [chosen]
        notice = picker.findChild(QLabel, "lblTimeframePinRefusal")
        assert notice is not None and notice.isVisibleTo(picker)
        path = out_dir / f"{BOTS_ROUTE}~interval-picker-chosen-pinned@1366x768.png"
        assert picker.grab().save(str(path)), path
        assert not is_blank(QImage(str(path)))
        picker.close()
