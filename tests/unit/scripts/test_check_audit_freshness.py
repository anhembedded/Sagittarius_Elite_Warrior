"""`EPIC-030L` — `stale_audits()` names every scheduled audit that went quiet.

Every test injects `today`; none reads the real clock.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.scripts.check_audit_freshness import (
    AUDITS,
    main,
    stale_audits,
)

_TODAY = date(2026, 10, 4)
_AUDIT_NAMES = [name for name, _skill in AUDITS]


def _report(root: Path, audit: str, name: str) -> None:
    directory = root / audit
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text("# report\n", encoding="utf-8")


def _all_reported_on(root: Path, day: str) -> None:
    for audit in _AUDIT_NAMES:
        _report(root, audit, f"{day}.md")


def test_reports_within_the_limit_are_fresh(tmp_path: Path) -> None:
    _all_reported_on(tmp_path, "2026-09-27")  # exactly 7 days: the boundary

    assert stale_audits(tmp_path, _TODAY, max_age_days=7) == []


def test_a_report_one_day_past_the_limit_is_stale(tmp_path: Path) -> None:
    _report(tmp_path, "test_health", "2026-09-26.md")  # 8 days
    _report(tmp_path, "process_drift", "2026-10-01.md")

    findings = stale_audits(tmp_path, _TODAY, max_age_days=7)

    assert len(findings) == 1
    assert findings[0].startswith("test_health:")
    assert "2026-09-26 is 8 days old" in findings[0]


def test_the_newest_report_decides(tmp_path: Path) -> None:
    _all_reported_on(tmp_path, "2026-08-01")
    _all_reported_on(tmp_path, "2026-10-03")

    assert stale_audits(tmp_path, _TODAY) == []


def test_a_missing_directory_never_ran(tmp_path: Path) -> None:
    _report(tmp_path, "test_health", "2026-10-03.md")

    findings = stale_audits(tmp_path, _TODAY)

    assert len(findings) == 1
    assert findings[0].startswith("process_drift:")
    assert "never ran" in findings[0]


@pytest.mark.parametrize(
    "name", ["baseline.json", "notes.md", "2026-10-03.txt", "2026-13-40.md"]
)
def test_files_that_are_not_dated_reports_are_ignored(
    tmp_path: Path, name: str
) -> None:
    for audit in _AUDIT_NAMES:
        _report(tmp_path, audit, name)

    findings = stale_audits(tmp_path, _TODAY)

    assert [finding.split(":")[0] for finding in findings] == _AUDIT_NAMES
    assert all("never ran" in finding for finding in findings)


def test_the_cli_exits_one_when_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _report(tmp_path, "test_health", "2026-10-03.md")

    status = main(["--today", "2026-10-04", "--reports-root", str(tmp_path)])

    assert status == 1
    assert "process_drift: never ran" in capsys.readouterr().out


def test_the_cli_exits_zero_when_fresh(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _all_reported_on(tmp_path, "2026-10-03")

    status = main(["--today", "2026-10-04", "--reports-root", str(tmp_path)])

    assert status == 0
    assert "All scheduled audits reported" in capsys.readouterr().out
