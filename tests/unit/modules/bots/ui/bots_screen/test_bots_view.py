"""`EPIC-029F` under `EPIC-033`'s desktop contract: the Bots screen is a
workbench host from birth, on the surface the shell declares."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BOTS_SURFACE,
    BotsView,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id


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
