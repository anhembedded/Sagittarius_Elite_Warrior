"""The kind-neutral backtest result and its port name no kind (`EPIC-040B`).

`BacktestOutcome` and its records (`domain/backtest/`), the `IKindBacktester` port and the
kind seam `IBotKind` are what the workbench (`EPIC-040D`) reads for every kind, and the workbench's own
package (`ui/backtest_workbench/`) is held to the same line. A Grid import there would make the
second kind's backtest a change to Grid code, and the workbench would branch on a kind again. So
none of them imports a kind: not `domain/grid`, not `application/kinds`, not `ui/kinds/<kind>`. The scan reuses `BOT-177`'s `files_importing_a_kind`.

There is no baseline: the files import no kind today, and a new import is a failure.

Retire when: never; the ban stays as long as the outcome is shared.
"""

from __future__ import annotations

from pathlib import Path

from .test_bots_services_stay_grouped import _REPO_ROOT, files_importing_a_kind

_BOTS = _REPO_ROOT / "src" / "modules" / "bots"
_NEUTRAL_FILES = (
    _BOTS / "contracts" / "i_kind_backtester.py",
    _BOTS / "contracts" / "i_bot_kind.py",
)


#: The editor's base class lives in the kinds' package but belongs to none of them: every kind
#: implements it and the workbench hosts whichever one the selected bot's kind gives it.
_SHARED_BY_KINDS = ("modules.bots.ui.kinds.bot_kind_panel",)


def _neutral_files() -> list[Path]:
    return sorted(
        [
            *(_BOTS / "domain" / "backtest").rglob("*.py"),
            *(_BOTS / "ui" / "backtest_workbench").rglob("*.py"),
            *_NEUTRAL_FILES,
        ]
    )


def test_the_kind_neutral_backtest_imports_no_kind() -> None:
    found = files_importing_a_kind(_neutral_files(), _REPO_ROOT, _SHARED_BY_KINDS)

    assert found == [], (
        f"these kind-neutral backtest files import a bot kind: {found}. Map the kind's "
        "result in its own adapter (`GridKindBacktester`) instead (`EPIC-040B`)."
    )


def test_the_guard_has_a_subject() -> None:
    files = _neutral_files()

    assert len(files) >= 15, files
    assert all(path.is_file() for path in files), [p for p in files if not p.is_file()]


def test_a_probe_importing_the_grid_into_the_outcome_turns_the_scan_red(
    tmp_path: Path,
) -> None:
    package = tmp_path / "src" / "modules" / "bots" / "domain" / "backtest"
    package.mkdir(parents=True)
    clean = package / "clean.py"
    clean.write_text("from decimal import Decimal\n", encoding="utf-8")
    prefix = "from Sagittarius_Elite_Warrior.src.modules.bots"
    for name, source in {
        "domain_grid.py": f"{prefix}.domain.grid.grid_plan import GridPlan\n",
        "kind_application.py": f"{prefix}.application.kinds.grid import grid_facts\n",
        "kind_screen.py": f"{prefix}.ui.kinds.grid.grid_panel import GridPanel\n",
    }.items():
        probe = package / name
        probe.write_text(source, encoding="utf-8")

        assert files_importing_a_kind([clean, probe], tmp_path) == [
            probe.relative_to(tmp_path).as_posix()
        ], name
