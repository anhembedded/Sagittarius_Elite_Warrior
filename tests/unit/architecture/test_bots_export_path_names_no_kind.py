"""The plan export is common to every bot kind and names none (`BOT-179`).

Export plan… writes any stored bot, whatever its kind: the kind and its config are
opaque data from the store to the file, and only the parser asks the kind catalog
whether a kind exists. So nothing on the export path imports a kind: not the plan
package, not the export query, not the file writer, not the command's UI (the shared
bots screen, its dialog and its flow). A Grid import there would make the second kind's
export a change to Grid code. The scan reuses `BOT-177`'s `files_importing_a_kind`.

There is no baseline: the path imports no kind today, and a new import is a failure.

Retire when: never; the ban stays as long as the export is shared.
"""

from __future__ import annotations

from pathlib import Path

from .test_bots_services_stay_grouped import _REPO_ROOT, files_importing_a_kind

_BOTS = _REPO_ROOT / "src" / "modules" / "bots"
_SCREEN = _BOTS / "ui" / "bots_screen"
_EXPORT_PATH = (
    _BOTS / "application" / "plan",
    _BOTS / "application" / "queries" / "export_bot_plan",
)
_EXPORT_FILES = (
    _BOTS / "adapters" / "plan_file.py",
    _SCREEN / "plan_export_flow.py",
    _SCREEN / "export_plan_dialog.py",
)


def _export_path_files() -> list[Path]:
    files = [path for package in _EXPORT_PATH for path in package.rglob("*.py")]
    return sorted([*files, *_EXPORT_FILES])


def test_the_export_path_imports_no_kind() -> None:
    found = files_importing_a_kind(_export_path_files(), _REPO_ROOT)

    assert found == [], (
        f"these files on the plan export path import a bot kind: {found}. The export "
        "takes `BotSnapshot.kind` and `config` as opaque data; ask `IBotKindCatalog` "
        "instead of importing the Grid (`BOT-179`)."
    )


def test_the_export_command_lives_in_the_shared_bots_screen_not_under_a_kind() -> None:
    commands = (_SCREEN / "bots_commands.py").read_text(encoding="utf-8")

    assert "EXPORT_PLAN" in commands
    under_a_kind = [
        path
        for path in (_BOTS / "ui" / "kinds").rglob("*.py")
        if "EXPORT_PLAN" in path.read_text(encoding="utf-8")
    ]
    assert under_a_kind == []


def test_the_guard_has_a_subject() -> None:
    files = _export_path_files()

    assert len(files) >= 8, files
    assert all(path.is_file() for path in files), [p for p in files if not p.is_file()]


def test_a_probe_importing_a_kind_on_the_export_path_turns_the_scan_red(
    tmp_path: Path,
) -> None:
    plan = tmp_path / "src" / "modules" / "bots" / "application" / "plan"
    plan.mkdir(parents=True)
    clean = plan / "clean.py"
    clean.write_text("from decimal import Decimal\n", encoding="utf-8")
    prefix = "from Sagittarius_Elite_Warrior.src.modules.bots"
    for name, source in {
        "domain_grid.py": f"{prefix}.domain.grid.grid_plan import GridPlan\n",
        "kind_application.py": f"{prefix}.application.kinds.grid import grid_facts\n",
        "kind_screen.py": f"{prefix}.ui.kinds.grid.grid_panel import GridPanel\n",
    }.items():
        probe = plan / name
        probe.write_text(source, encoding="utf-8")

        assert files_importing_a_kind([clean, probe], tmp_path) == [
            probe.relative_to(tmp_path).as_posix()
        ], name
