"""`TimeframeSelection` — the state both timeframe views share.

## Restated from a suite the gate never ran

`TimeframeVM` had 12 tests at `src/support/charting/TimeframePicker/tests/`,
under `src/`, where the gate's `pytest tests` does not collect them. `CS-004`
for the fourth time this phase; all twelve are restated here, where it does.

They read the same, minus the `QVariantList` dicts: a row is a frozen dataclass
now, so `row.code` replaces `row["code"]` and a missing key is an error at the
point of writing rather than a `None` at the point of rendering.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.support.charting.timeframe_picker import (
    TimeframeSelection,
)


class _Host:
    """A screen: the codes it offers, the interval it is on, and its pinned
    set — the four callbacks a selection is built from, in one object so a
    test can change any of them between refreshes."""

    def __init__(
        self, codes: list[str], current: str = "", pinned: list[str] | None = None
    ):
        self.codes = codes
        self.current = current
        self.pinned = list(pinned or [])
        self.writes: list[tuple[str, bool]] = []

    def set_pinned(self, code: str, pinned: bool) -> None:
        self.writes.append((code, pinned))
        if pinned:
            self.pinned.append(code)
        else:
            self.pinned.remove(code)

    def build(self) -> TimeframeSelection:
        selection = TimeframeSelection(
            get_codes=lambda: self.codes,
            get_current=lambda: self.current,
            get_pinned=lambda: self.pinned,
            set_pinned=self.set_pinned,
        )
        selection.refresh()
        return selection


@pytest.fixture
def host():
    return _Host(codes=["1h", "1m", "1s", "4h"], current="1h", pinned=["4h", "1m"])


def test_refresh_builds_pinned_rows_in_catalogue_order(host):
    """Catalogue order is duration order, not the order the host happened to
    pin them in — the pill row reads this straight through."""
    selection = host.build()

    assert [row.code for row in selection.pinned_rows] == ["1m", "4h"]


def test_the_current_code_is_marked_on_exactly_one_pinned_row(host):
    host.current = "4h"
    selection = host.build()

    assert [row.code for row in selection.pinned_rows if row.current] == ["4h"]


def test_refresh_builds_groups_with_labels_and_captions(host):
    selection = host.build()

    assert [group.label for group in selection.groups]
    assert all(group.caption for group in selection.groups)
    assert all(group.rows for group in selection.groups), "an empty group is dropped"


def test_every_offered_code_appears_exactly_once_across_the_groups(host):
    selection = host.build()

    codes = [row.code for group in selection.groups for row in group.rows]
    assert sorted(codes) == sorted(host.codes)


def test_has_warning_only_when_a_sub_minute_timeframe_is_offered(host):
    with_seconds = host.build()
    host.codes = ["1h", "4h"]
    without = host.build()

    assert with_seconds.has_warning is True
    assert without.has_warning is False


def test_choose_updates_the_current_code_and_emits(host):
    selection = host.build()
    heard: list[str] = []
    selection.chosen.connect(heard.append)

    selection.choose("4h")

    assert heard == ["4h"]
    assert selection.current_code == "4h"


def test_choose_ignores_a_code_that_is_not_offered(host):
    selection = host.build()
    heard: list[str] = []
    selection.chosen.connect(heard.append)

    selection.choose("2w")

    assert heard == []
    assert selection.current_code == "1h"


def test_set_current_updates_the_highlight_without_emitting(host):
    """`ChartToolbar.set_active()`'s contract: a caller that already knows the
    new interval must not have it echoed back as a choice."""
    selection = host.build()
    heard: list[str] = []
    selection.chosen.connect(heard.append)

    selection.set_current("4h")

    assert heard == []
    assert selection.current_code == "4h"


def test_set_current_accepts_a_code_outside_the_offered_set(host):
    """A stale config entry still updates `current_code` faithfully rather
    than being silently dropped. It simply highlights nothing."""
    selection = host.build()

    selection.set_current("2w")

    assert selection.current_code == "2w"
    assert [row.code for row in selection.pinned_rows if row.current] == []


def test_set_current_with_none_reports_an_empty_current_code(host):
    selection = host.build()

    selection.set_current(None)

    assert selection.current_code == ""


def test_toggle_pinned_adds_removes_and_writes_through_to_the_host(host):
    """`set_pinned` is a write-through call, not a signal the host might
    ignore: the pinned set belongs to whatever persists it."""
    selection = host.build()

    selection.toggle_pinned("1h")
    assert host.writes == [("1h", True)]
    assert "1h" in {row.code for row in selection.pinned_rows}

    selection.toggle_pinned("1h")
    assert host.writes == [("1h", True), ("1h", False)]
    assert "1h" not in {row.code for row in selection.pinned_rows}


def test_toggle_pinned_ignores_a_code_that_is_not_offered(host):
    selection = host.build()

    selection.toggle_pinned("2w")

    assert host.writes == []


def test_pinning_shows_in_the_groups_view_too(host):
    """The one hard requirement, at the state level: both views read one
    object, so a pin made through either is true for both."""
    selection = host.build()

    selection.toggle_pinned("1h")

    pinned_in_groups = {
        row.code for group in selection.groups for row in group.rows if row.pinned
    }
    assert pinned_in_groups == {"1m", "4h", "1h"}


def test_every_change_announces_itself_once(host):
    selection = host.build()
    changes: list[int] = []
    selection.stateChanged.connect(lambda: changes.append(1))

    selection.choose("4h")
    selection.toggle_pinned("1h")
    selection.set_current("1m")

    assert len(changes) == 3
