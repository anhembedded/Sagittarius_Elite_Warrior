"""`EPIC-029F` under `EPIC-033`'s desktop contract: the Bots screen is a
workbench host from birth, on the surface the shell declares."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    BotFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BOTS_SURFACE,
    BotsView,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id
from sagittarius_engine.extensions.pyside_mvc.workbench import ReadoutForm


def test_bots_view_renders_the_surface_the_shell_declares(qapp) -> None:
    """The view declares its `Surface` because a module may not import
    `shell/`; this test is what keeps that one declaration, not two."""
    assert surfaces_by_id()["bots"] == BOTS_SURFACE


def test_the_screen_is_a_workbench_host_holding_the_list_and_the_detail(
    qapp,
) -> None:
    view = BotsView()
    try:
        hosts = view.findChildren(QMainWindow)
        assert len(hosts) == 1
        workspace = hosts[0].centralWidget()
        assert workspace is not None
        assert workspace.isAncestorOf(view.table)
        assert workspace.isAncestorOf(view.detail)
    finally:
        view.deleteLater()


def test_the_bots_figures_are_a_read_out(qapp) -> None:
    """`EPIC-033N`: label–value figures are the Engine's `ReadoutForm`."""
    view = BotsView()
    try:
        view.model.set_facts(
            BotFacts(
                state="Running",
                venue="SPOT_TESTNET",
                symbol="BTCUSDT",
                capital="500",
                grid_profit="12.50",
                unrealised="10.00 at 65,000.00",
                inventory="0.01 at an average 64,000.00",
                running_time="1h 05m",
            )
        )

        facts = view.detail.facts
        assert isinstance(facts, ReadoutForm)
        assert facts.value_text("symbol") == "BTCUSDT"
        assert facts.value_text("unrealised") == "10.00 at 65,000.00"

        view.model.set_facts(None)
        assert facts.value_text("symbol") == ""
    finally:
        view.deleteLater()
