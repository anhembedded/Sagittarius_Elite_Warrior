"""`BUG-146` — `run-ui.ps1` launches a file that actually starts the app.

`scripts/run-ui.ps1` runs one Python file as a script. It named
`src/presentation/ui/main_window.py`, which started the app only through a
legacy `if __name__ == "__main__"` block forwarding to
`app_bootstrapper.main()`. `EPIC-033C` rewrote `main_window.py` without that
block, so the launcher imported the module and exited: no window, no error.
No tier noticed, because the sanity tier starts the app with
`python -m ...app_bootstrapper`, not the way the launcher does.

This reads the launcher's own entry path and checks that file starts the
app: it exists and has a `__main__` block that calls `main()`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_LAUNCHER = _ROOT / "scripts" / "run-ui.ps1"
_ENTRY_LINE = re.compile(r"^\$UIEntry\s*=\s*\[System\.IO\.Path\]::Combine\((.+)\)\s*$")


def _launched_file() -> Path:
    for line in _LAUNCHER.read_text(encoding="utf-8").splitlines():
        match = _ENTRY_LINE.match(line.strip())
        if match:
            parts = [part.strip().strip('"') for part in match.group(1).split(",")]
            assert parts[0] == "$BotRoot", f"unexpected entry root: {parts[0]}"
            return _ROOT.joinpath(*parts[1:])
    raise AssertionError(f"no $UIEntry line in {_LAUNCHER}")


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


def test_the_launcher_runs_a_file_that_starts_the_app() -> None:
    entry = _launched_file()

    assert entry.is_file(), f"run-ui.ps1 launches {entry}, which does not exist"
    tree = ast.parse(entry.read_text(encoding="utf-8"))
    assert _main_block_calls_main(tree), (
        f"run-ui.ps1 launches {entry.relative_to(_ROOT)}, which has no "
        '`if __name__ == "__main__": main()` block: the launcher would '
        "import it and exit without opening a window."
    )
