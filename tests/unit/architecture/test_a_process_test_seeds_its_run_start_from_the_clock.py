"""A process test seeds a run's start from the real clock, never from a fixed date (`BUG-278`).

The host a `presentation` process test launches reads the real clock, and a run older than
`MAX_HISTORY_LOOKBACK` (30 days) reconciles another way: a fixed `run_started_at` is true until
the calendar passes it (`pitfalls/tests.md` #9).

Limit: a stop-gap. It reads one directory and matches by file (`run_started_at` and `datetime(20xx,`
in the same file); it does not see `fromisoformat`, `date(...)` or `tests/integration/modules/`.
"""

import re
from pathlib import Path

PRESENTATION_TESTS = (
    Path(__file__).resolve().parents[2] / "integration" / "presentation"
)
FIXED_DATE = re.compile(r"datetime\(\s*20\d\d\s*,")


def test_a_presentation_test_that_seeds_a_run_start_writes_no_fixed_date() -> None:
    offenders = [
        path.name
        for path in sorted(PRESENTATION_TESTS.glob("*.py"))
        if "run_started_at" in (text := path.read_text(encoding="utf-8"))
        and FIXED_DATE.search(text)
    ]
    assert not offenders, (
        f"{offenders} seed run_started_at beside a fixed datetime(20xx, ...): use "
        "datetime.now(UTC) - timedelta(days=1) (BUG-278)"
    )
