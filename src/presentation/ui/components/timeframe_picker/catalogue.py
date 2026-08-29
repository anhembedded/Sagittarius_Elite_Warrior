"""Every timeframe the domain knows, ordered, grouped and named in Vietnamese.

@par Why this is derived from `TimeFrame` rather than listed here
The app used to offer five timeframes — `DEFAULT_TIMEFRAMES`, a tuple in
`chart_card/chart_toolbar.py` — while `TimeFrame` declared sixteen. That tuple
is a *toolbar* row (five pills that have to fit in a chart header), and it was
doing double duty as the *picker's* option list, so eleven timeframes the
domain, the exchange and the database all supported were unreachable from the
UI.

Deriving the list here means adding a member to `TimeFrame` puts it in the
picker with no second edit, which is the only version of this that cannot
drift back apart.

Pure data: no Qt import, so the ordering and the labels are testable without
a `QApplication`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .....domain.value_objects.timeframe import TimeFrame


class TimeframeGroup(Enum):
    """Which section of the picker a timeframe belongs in.

    @details Grouping by unit rather than showing sixteen equal cells: the
    unit is the first thing a user decides ("I want hours"), and the number
    only after.
    """

    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"


#: Section heading per group, in display order.
GROUP_LABELS: dict[TimeframeGroup, str] = {
    TimeframeGroup.SECONDS: "GIÂY",
    TimeframeGroup.MINUTES: "PHÚT",
    TimeframeGroup.HOURS: "GIỜ",
    TimeframeGroup.DAYS: "NGÀY TRỞ LÊN",
}

#: Short annotation shown beside each section heading in the QML picker
#: (`qml/TimeframePicker/`) — context a bare "PHÚT" does not give: which
#: section is heavy, which is the sane default, which suits a scalper versus
#: a swing trader. Additive only: `TimeframePickerOverlay` (the QtWidgets
#: dialog) does not read this, so it does not change what that dialog shows.
GROUP_CAPTIONS: dict[TimeframeGroup, str] = {
    TimeframeGroup.SECONDS: "dữ liệu tick — nặng",
    TimeframeGroup.MINUTES: "mặc định cho scalping",
    TimeframeGroup.HOURS: "intraday",
    TimeframeGroup.DAYS: "swing / vị thế dài",
}

#: Unit suffix → (group, Vietnamese noun). Keyed by the same last character
#: `TimeFrame.to_seconds()` switches on, so a member this map does not cover
#: is a member that has no duration either — `test_every_timeframe_is_named`
#: fails rather than the picker silently dropping it.
_UNITS: dict[str, tuple[TimeframeGroup, str]] = {
    "s": (TimeframeGroup.SECONDS, "giây"),
    "m": (TimeframeGroup.MINUTES, "phút"),
    "h": (TimeframeGroup.HOURS, "giờ"),
    "d": (TimeframeGroup.DAYS, "ngày"),
    "w": (TimeframeGroup.DAYS, "tuần"),
    "M": (TimeframeGroup.DAYS, "tháng"),
}

#: Below this, one day of history is tens of thousands of candles. Not a
#: block — `1s` is exactly what `VolumeSpikeFlowStrategy` needs — but the
#: picker says so, because choosing it and then waiting on a sync that looks
#: hung is how this gets reported as a bug.
_HEAVY_MAX_SECONDS = 60


@dataclass(frozen=True, slots=True)
class TimeframeOption:
    """One choosable timeframe: the exchange's code, and how to render it."""

    code: str
    label: str
    group: TimeframeGroup
    seconds: int

    @property
    def is_high_resolution(self) -> bool:
        """Whether a normal date range on this timeframe is a very large
        number of candles, and the picker should warn before it is picked."""
        return self.seconds < _HEAVY_MAX_SECONDS


#: Every code the domain declares. Membership is the definition of "is a
#: timeframe" here: this catalogue offers what the domain, the exchange and
#: the database all already support, and nothing else.
_CODES: frozenset[str] = frozenset(member.value for member in TimeFrame)


def describe(code: str) -> TimeframeOption | None:
    """The option for one exchange code, or `None` when the domain has no
    such timeframe.

    @details Returns `None` rather than raising: the codes reaching this come
    from a ViewModel, and ultimately from remembered state on disk, so a
    value that no longer parses has to degrade to "not offered" the same way
    a delisted symbol does.
    """
    if code not in _CODES:
        return None
    unit = _UNITS.get(code[-1])
    if unit is None:  # pragma: no cover - guarded by test_every_timeframe_is_named
        return None
    group, noun = unit
    return TimeframeOption(
        code=code,
        label=f"{int(code[:-1])} {noun}",
        group=group,
        seconds=TimeFrame(code).to_seconds(),
    )


def all_options() -> list[TimeframeOption]:
    """Every timeframe the domain declares, shortest first.

    @details Sorted by duration rather than by declaration order, so the
    sequence stays correct however `TimeFrame`'s members are later reordered.
    """
    options = [describe(code) for code in _CODES]
    return sorted(
        (option for option in options if option is not None),
        key=lambda option: option.seconds,
    )


def options_for(codes: object) -> list[TimeframeOption]:
    """The subset of the catalogue a screen actually offers, in catalogue order.

    @param codes Whatever the screen's ViewModel exposes. Anything that is not
        a recognised code is dropped, so a screen restricting the list cannot
        put an unrenderable cell in the grid.
    """
    if not isinstance(codes, (list, tuple)):
        return []
    wanted = {str(code) for code in codes}
    return [option for option in all_options() if option.code in wanted]


def group_options(
    options: list[TimeframeOption],
) -> list[tuple[TimeframeGroup, list[TimeframeOption]]]:
    """`options` split into sections, in `GROUP_LABELS` order, empty groups
    dropped — a heading with nothing under it is worse than no heading."""
    grouped: list[tuple[TimeframeGroup, list[TimeframeOption]]] = []
    for group in GROUP_LABELS:
        members = [option for option in options if option.group is group]
        if members:
            grouped.append((group, members))
    return grouped
