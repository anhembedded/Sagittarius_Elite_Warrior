"""`BUG-146` — `run.ps1` launches files that actually start the app.

`scripts/run.ps1` (the one launcher since `BOT-175`; `-UI` is its default) runs
one Python file as a script. It named
`src/presentation/ui/main_window.py`, which started the app only through a
legacy `if __name__ == "__main__"` block forwarding to
`app_bootstrapper.main()`. `EPIC-033C` rewrote `main_window.py` without that
block, so the launcher imported the module and exited: no window, no error.
No tier noticed, because the sanity tier starts the app with
`python -m ...app_bootstrapper`, not the way the launcher does.

This reads the launcher's own entry paths and checks each file starts the
app: it exists and has a `__main__` block that calls `main()`. It also locks
the launcher's contract (`BOT-175`): `-UI`, `-CLI`, pass-through of the
remaining arguments, the exit code, and, when `pwsh` is installed, that
`-UI -CLI` fails before any Python starts.
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_LAUNCHER = _ROOT / "scripts" / "run.ps1"
_ENTRY_LINE = re.compile(r"^\s*\$Entry\s*=\s*\[System\.IO\.Path\]::Combine\((.+)\)\s*$")


def _launched_files() -> list[Path]:
    """Every `$Entry = [System.IO.Path]::Combine($BotRoot, ...)` the script has:
    one per mode (`-CLI`, `-UI`)."""
    files = []
    for line in _LAUNCHER.read_text(encoding="utf-8").splitlines():
        match = _ENTRY_LINE.match(line)
        if match:
            parts = [part.strip().strip('"') for part in match.group(1).split(",")]
            assert parts[0] == "$BotRoot", f"unexpected entry root: {parts[0]}"
            files.append(_ROOT.joinpath(*parts[1:]))
    assert files, f"no $Entry line in {_LAUNCHER}"
    return files


def _main_block_calls_main(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == "__main__"
        ):
            continue
        for statement in ast.walk(node):
            if (
                isinstance(statement, ast.Call)
                and isinstance(statement.func, ast.Name)
                and statement.func.id == "main"
            ):
                return True
    return False


def test_the_launcher_runs_files_that_start_the_app() -> None:
    entries = _launched_files()

    assert {entry.name for entry in entries} == {"main.py", "app_bootstrapper.py"}
    for entry in entries:
        assert entry.is_file(), f"run.ps1 launches {entry}, which does not exist"
        tree = ast.parse(entry.read_text(encoding="utf-8"))
        assert _main_block_calls_main(tree), (
            f"run.ps1 launches {entry.relative_to(_ROOT)}, which has no "
            '`if __name__ == "__main__": main()` block: the launcher would '
            "import it and exit without starting."
        )


def test_the_launcher_declares_both_modes_and_passes_the_rest_through() -> None:
    text = _LAUNCHER.read_text(encoding="utf-8")

    assert "[switch]$UI" in text
    assert "[switch]$CLI" in text
    # Unbound arguments (`$args`) reach src/main.py as they are.
    assert "$ForwardedArgs = @($args)" in text
    assert "@EntryArgs" in text
    assert "$EntryArgs = $ForwardedArgs" in text
    # The Python process's exit code is the script's.
    assert text.rstrip().endswith("exit $LASTEXITCODE")
    assert not (_ROOT / "scripts" / "run-ui.ps1").exists(), "one start point only"


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="pwsh is not installed")
def test_ui_and_cli_together_fail_before_any_python_starts() -> None:
    result = subprocess.run(
        [
            str(shutil.which("pwsh")),
            "-NoProfile",
            "-File",
            str(_LAUNCHER),
            "-UI",
            "-CLI",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode != 0
    assert "mutually exclusive" in result.stderr
    # No venv step ran: the refusal comes before any output of the setup.
    assert "Creating virtual environment" not in result.stdout
    assert "Installing" not in result.stdout
