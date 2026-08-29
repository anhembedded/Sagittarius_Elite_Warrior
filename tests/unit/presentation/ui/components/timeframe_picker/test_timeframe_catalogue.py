"""Tests for the timeframe catalogue — pure, no QApplication needed."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.components.timeframe_picker import (
    GROUP_CAPTIONS,
    GROUP_LABELS,
    TimeframeGroup,
    all_options,
    describe,
    group_options,
    options_for,
)


def test_every_domain_timeframe_is_offered():
    """The whole point of `EPIC-013`: the picker used to offer 5 of 16."""
    codes = [option.code for option in all_options()]

    assert sorted(codes) == sorted(member.value for member in TimeFrame)


def test_every_timeframe_is_named():
    """A member whose unit suffix the catalogue does not cover would be
    dropped silently — the picker would just be short one cell."""
    for member in TimeFrame:
        option = describe(member.value)
        assert option is not None, member.value
        assert option.label.strip() != ""


def test_options_are_ordered_by_duration_not_declaration():
    seconds = [option.seconds for option in all_options()]

    assert seconds == sorted(seconds)
    assert [o.code for o in all_options()][:3] == ["1s", "1m", "3m"]


def test_the_month_code_is_not_confused_with_the_minute_code():
    """`1m` and `1M` differ only in case, and `to_seconds()` switches on that
    same character — a case-insensitive lookup here would make one of them
    render as the other."""
    assert describe("1m").label == "1 phút"
    assert describe("1M").label == "1 tháng"
    assert describe("1m").group is TimeframeGroup.MINUTES
    assert describe("1M").group is TimeframeGroup.DAYS


def test_weeks_and_months_share_the_day_section():
    """Three sections of one cell each would be worse than one section of
    four."""
    groups = {
        option.group for option in all_options() if option.code in {"1d", "1w", "1M"}
    }

    assert groups == {TimeframeGroup.DAYS}


def test_only_sub_minute_timeframes_are_flagged_high_resolution():
    flagged = [o.code for o in all_options() if o.is_high_resolution]

    assert flagged == ["1s"]


def test_an_unknown_code_is_not_a_timeframe():
    """Codes reach this from remembered state on disk, so a value that no
    longer parses must degrade rather than raise."""
    assert describe("7d") is None
    assert describe("banana") is None
    assert describe("m") is None
    assert describe("") is None


def test_options_for_narrows_the_catalogue_and_keeps_its_order():
    chosen = options_for(["1d", "5m", "nonsense"])

    assert [option.code for option in chosen] == ["5m", "1d"]


def test_options_for_tolerates_a_non_list():
    """`timeframeOptions` is a Qt `QStringList` property; a ViewModel double
    can hand back anything at all."""
    assert options_for(None) == []
    assert options_for("1m") == []


def test_grouping_drops_empty_sections():
    grouped = group_options(options_for(["1h", "4h"]))

    assert [group for group, _ in grouped] == [TimeframeGroup.HOURS]
    assert [option.code for _, options in grouped for option in options] == ["1h", "4h"]


def test_grouping_follows_the_declared_section_order():
    grouped = group_options(all_options())

    assert [group for group, _ in grouped] == list(GROUP_LABELS)


def test_every_group_has_a_caption():
    """A group added to `GROUP_LABELS` without one here would render the
    QML picker's section caption as an empty string with no warning."""
    assert set(GROUP_CAPTIONS) == set(GROUP_LABELS)
    for caption in GROUP_CAPTIONS.values():
        assert caption.strip() != ""
