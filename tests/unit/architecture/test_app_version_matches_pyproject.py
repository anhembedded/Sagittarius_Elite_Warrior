"""The version the app shows is the version the project declares.

`app.version` in `src/config/app_config.json` is what the Welcome screen
displays (PR 1.5a), and `pyproject.toml`'s `version` is what the project *is*.
Two places holding one number drift — this is the guard that makes the drift a
failing test instead of a wrong number on the first screen the user sees.

Why the value is in configuration at all rather than read from installed
package metadata: this application runs from a checkout, not from a wheel, so
`importlib.metadata` has nothing to answer with. Why not a constant in the
widget: the shell shows it, and the shell may not import the legacy tree where
the window title lives.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_APP_CONFIG = _REPO_ROOT / "src" / "config" / "app_config.json"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

#: `version = "0.1.0"` in the `[project]` table. A regex rather than a TOML
#: parser because the only line that matters is unambiguous, and `tomllib` on
#: the whole file would read the tool tables this test has no business in.
_VERSION_LINE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def _configured() -> dict[str, object]:
    return json.loads(_APP_CONFIG.read_text(encoding="utf-8"))


def test_the_configured_version_is_the_projects_version() -> None:
    match = _VERSION_LINE.search(_PYPROJECT.read_text(encoding="utf-8"))
    assert match is not None, "pyproject.toml has no [project] version line"

    assert _configured()["app.version"] == match.group(1), (
        "`app.version` in app_config.json and `version` in pyproject.toml "
        "disagree. Bump both in the same commit — the first is what the "
        "Welcome screen shows the user."
    )


def test_the_app_has_a_name_to_show() -> None:
    assert _configured()["app.name"]
