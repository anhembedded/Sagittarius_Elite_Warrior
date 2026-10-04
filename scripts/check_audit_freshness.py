"""Report the scheduled audits that have gone quiet (`EPIC-030L`).

`ONBOARDING.md` §13 says every scheduled audit run writes a dated report under
`Tasks/reports/` and that silence is never success. Nothing checked it: the
2026-10-04 audit found `test_health` silent for 27 days and `process_drift`
never run at all, with no alarm. This script is that alarm; the
`audit-freshness` GitHub workflow runs it daily and files an issue when it
reports anything.

An audit is fresh when its directory holds a `YYYY-MM-DD.md` report dated at
most `max_age_days` before `today`. Other files (`baseline.json`, notes) are
ignored; a missing directory means the audit never ran.

Usage:
    python3 scripts/check_audit_freshness.py [--today YYYY-MM-DD]
        [--max-age-days N] [--reports-root DIR]

Exit status 1 when an audit is stale, 0 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path

#: The scheduled audits, by their report directory under `Tasks/reports/`,
#: each with the skill that writes it. One line per new audit.
AUDITS: tuple[tuple[str, str], ...] = (
    ("test_health", ".claude/skills/test-health/SKILL.md"),
    ("process_drift", ".claude/skills/process-drift/SKILL.md"),
)
DEFAULT_MAX_AGE_DAYS = 7

_REPORT_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def repo_root() -> Path:
    """The repository root, found by landmark rather than by hop count."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("pyproject.toml not found above this script")


def newest_report_date(directory: Path) -> date | None:
    """The date of the newest `YYYY-MM-DD.md` in `directory`, or `None`."""
    dates: list[date] = []
    for path in directory.iterdir():
        match = _REPORT_NAME.match(path.name)
        if match is None or not path.is_file():
            continue
        try:
            dates.append(date.fromisoformat(match.group(1)))
        except ValueError:
            continue  # e.g. 2026-13-40.md: shaped like a report, not one
    return max(dates, default=None)


def stale_audits(
    reports_root: Path, today: date, max_age_days: int = DEFAULT_MAX_AGE_DAYS
) -> list[str]:
    """One line per audit whose newest report is older than `max_age_days`
    (or that has none); empty when every audit is fresh."""
    findings: list[str] = []
    for name, skill in AUDITS:
        directory = reports_root / name
        newest = newest_report_date(directory) if directory.is_dir() else None
        if newest is None:
            findings.append(
                f"{name}: never ran (no dated report under {name}/; {skill})"
            )
            continue
        age = (today - newest).days
        if age > max_age_days:
            findings.append(
                f"{name}: last report {newest.isoformat()} is {age} days old "
                f"(limit {max_age_days}; {skill})"
            )
    return findings


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report the scheduled audits that have gone quiet."
    )
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=None,
        help="the date to judge against (default: today, UTC)",
    )
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    parser.add_argument(
        "--reports-root",
        type=Path,
        default=None,
        help="the reports directory (default: <repo>/Tasks/reports)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    today: date = args.today if args.today is not None else datetime.now(tz=UTC).date()
    reports_root: Path = (
        args.reports_root
        if args.reports_root is not None
        else repo_root() / "Tasks" / "reports"
    )
    findings = stale_audits(reports_root, today, args.max_age_days)
    if not findings:
        print(
            f"All scheduled audits reported within {args.max_age_days} days of {today}."
        )
        return 0
    print(f"Stale scheduled audits as of {today}:")
    for finding in findings:
        print(f"- {finding}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
