"""`EPIC-047E` (AC7, charter O4) - the VPS Bots tab is built from the Bots screen's own classes, not a copy of them.

**Why.** The owner asked for the same tab on another backend: a copied screen drifts, and a subclass that overrides a method
is a second screen in all but name. The tab's contribution must name the Bots screen's view and presenter factories, and its
commands must be the Bots screen's own list under other ids, so a command added to the Bots tab is in the VPS tab by itself.

**What it checks.** The two screens' view factory is the same dotted target; the VPS builder hands the Bots presenter its
container (the builder file names that target and no other presenter class); the VPS tab defines no class that derives from
the Bots view or presenter; and every Bots command has its VPS twin.

Retire when: the Bots screen is parameterised by a route and the shell contributes it twice.
"""

from __future__ import annotations

import ast
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    bots_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    bots_screen,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.vps_command_ids import (
    vps_command_id,
    vps_commands,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import VPS_BOTS_SURFACE_ID
from Sagittarius_Elite_Warrior.src.shell.vps_tab.vps_tab_screen import vps_bots_screen

_SRC = Path(__file__).resolve().parents[3] / "src"
_BOTS_PRESENTER = "bots_presenter:BotsPresenter"
_VPS_FILES = (
    *(_SRC / "shell" / "vps_tab").glob("*.py"),
    *(_SRC / "modules" / "bots" / "ui" / "bots_screen" / "vps").glob("*.py"),
    *(_SRC / "modules" / "bots" / "ui" / "bots_screen").glob("vps_*.py"),
)


def test_both_tabs_build_the_same_view_class() -> None:
    assert vps_bots_screen().view_factory is not None
    assert (
        vps_bots_screen().view_factory.target == bots_screen().view_factory.target  # type: ignore[attr-defined]
    )


def test_the_vps_builder_builds_the_bots_presenter_and_no_other() -> None:
    source = (_SRC / "shell" / "vps_tab" / "vps_tab_builder.py").read_text(
        encoding="utf-8"
    )

    assert _BOTS_PRESENTER in source
    assert "class " not in source


def test_no_vps_file_derives_a_class_from_the_bots_view_or_presenter() -> None:
    derived = []
    for path in _VPS_FILES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {ast.unparse(base) for base in node.bases}
            if bases & {"BotsView", "BotsPresenter"}:
                derived.append(f"{path.name}: {node.name}")

    assert derived == []


def test_every_bots_command_has_its_vps_twin_in_the_vps_mode() -> None:
    bots = bots_commands("bots")
    twins = vps_commands("vps_bots")

    assert [vps_command_id(command.command_id) for command in bots] == [
        command.command_id for command in twins
    ]
    assert {command.mode for command in twins} == {"vps_bots"}


def test_the_tabs_route_is_the_id_of_its_own_surface() -> None:
    assert vps_bots_screen().route == VPS_BOTS_SURFACE_ID
