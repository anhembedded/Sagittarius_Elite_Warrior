"""Regression test for `BUG-080`'s second, independent problem: API Key/
Secret used to be written to `user_config.json`, a git-tracked file
(`git ls-files src/config/` includes it). Written before the fix, per
`bug-fix-rule.md`: confirmed failing (both keys present, and
`settings_presenter.py` calling `IConfig.set("API_KEY", ...)`) on the code
as `EPIC-021B` found it.

Two checks, two different classes of regression:
  1. `user_config.json` itself never ships the two keys again.
  2. No source file anywhere under `src/` calls `.set("API_KEY", ...)` /
     `.set("API_SECRET", ...)` — not just `settings_presenter.py` today, but
     any future call site that would reintroduce the same mistake.
"""

from __future__ import annotations

import json
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parents[3] / "src"
_CONFIG_DIR = _SRC_DIR / "config"

_FORBIDDEN_SET_CALLS = (
    '.set("API_KEY"',
    ".set('API_KEY'",
    '.set("API_SECRET"',
    ".set('API_SECRET'",
)


def test_user_config_json_no_longer_ships_credential_keys() -> None:
    user_config = json.loads((_CONFIG_DIR / "user_config.json").read_text())
    assert "API_KEY" not in user_config
    assert "API_SECRET" not in user_config


def test_no_source_file_writes_credentials_through_iconfig_set() -> None:
    offenders = []
    for path in _SRC_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(pattern in text for pattern in _FORBIDDEN_SET_CALLS):
            offenders.append(str(path.relative_to(_SRC_DIR)))

    assert offenders == [], (
        "These files still write API_KEY/API_SECRET through IConfig.set(), "
        f"which lands in the git-tracked user_config.json: {offenders}. "
        "Use IExchangeCredentialsProvider.save_to_file() instead — it writes "
        "to the gitignored secrets.local.json."
    )
