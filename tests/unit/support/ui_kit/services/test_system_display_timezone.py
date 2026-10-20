"""`BUG-234`: "System" shows the machine's own time, not UTC, on a machine whose
zone name is not an IANA key (`+07`, `EDT`, `BST`).

The machine is injected through `machine_local_time`, the one place the service asks
the OS, so no test depends on the runner's `TZ` (and none needs `time.tzset`, which
Windows lacks)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestRunConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.run_texts import (
    time_range_diff_text,
    zoned_moment_text,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services import (
    display_timezone_service as service,
)

_PAUSE_END = datetime(2026, 10, 19, 12, 1, 30, tzinfo=UTC)
_JANUARY = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC).timestamp()
_JULY = datetime(2026, 7, 15, 12, 0, 0, tzinfo=UTC).timestamp()


def _machine_in(iana_key: str) -> Callable[[datetime], datetime]:
    """What the OS answers on a machine set to `iana_key`: the moment, in that zone's rules,
    as the fixed-offset zone `datetime.astimezone()` returns: named by the abbreviation
    (`+07`, `EDT`), never by the key."""
    zone = ZoneInfo(iana_key)

    def local_time(moment: datetime) -> datetime:
        local = moment.astimezone(zone)
        offset = local.utcoffset()
        assert offset is not None
        return local.astimezone(timezone(offset, local.tzname()))

    return local_time


@pytest.mark.parametrize(
    ("iana_key", "shown", "abbreviation"),
    [
        ("Asia/Ho_Chi_Minh", "2026-10-19 19:01:30", "+07"),
        ("America/New_York", "2026-10-19 08:01:30", "EDT"),
        ("Europe/London", "2026-10-19 13:01:30", "BST"),
    ],
)
def test_system_shows_the_machines_own_time(
    monkeypatch: pytest.MonkeyPatch, iana_key: str, shown: str, abbreviation: str
) -> None:
    monkeypatch.setattr(service, "machine_local_time", _machine_in(iana_key))

    assert (
        service.format_display_datetime(_PAUSE_END, service.SYSTEM_TIMEZONE_KEY)
        == shown
    )
    assert abbreviation in service.get_display_timezone_label(
        service.SYSTEM_TIMEZONE_KEY
    )


def test_system_follows_daylight_saving_per_instant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A backtest range in July shown in January is still July's offset."""
    monkeypatch.setattr(service, "machine_local_time", _machine_in("America/New_York"))

    key = service.SYSTEM_TIMEZONE_KEY
    assert service.get_utc_offset_seconds(_JANUARY, key) == -5 * 3600.0
    assert service.get_utc_offset_seconds(_JULY, key) == -4 * 3600.0


def test_system_zone_is_named_by_the_text_that_was_written_in_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "machine_local_time", _machine_in("Asia/Ho_Chi_Minh"))

    text = zoned_moment_text(_PAUSE_END, service.SYSTEM_TIMEZONE_KEY)

    assert text == "2026-10-19 19:01:30 UTC+07:00"


def test_a_machine_that_cannot_answer_falls_back_to_utc_and_says_so(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(moment: datetime) -> datetime:
        raise OSError("no local time")

    monkeypatch.setattr(service, "machine_local_time", broken)
    monkeypatch.setattr(service, "_reported_fallbacks", set())

    with caplog.at_level(logging.WARNING, logger="App.DisplayTimezone"):
        shown = service.format_display_datetime(_PAUSE_END, service.SYSTEM_TIMEZONE_KEY)

    assert shown == "2026-10-19 12:01:30"
    assert "falling back to UTC" in caplog.text


def test_the_fallback_is_logged_once_not_once_per_cell(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(moment: datetime) -> datetime:
        raise OSError("no local time")

    monkeypatch.setattr(service, "machine_local_time", broken)
    monkeypatch.setattr(service, "_reported_fallbacks", set())

    with caplog.at_level(logging.WARNING, logger="App.DisplayTimezone"):
        for _ in range(50):
            service.format_display_datetime(_PAUSE_END, service.SYSTEM_TIMEZONE_KEY)

    assert len(caplog.records) == 1


def test_utc_machine_is_named_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        service, "machine_local_time", lambda moment: moment.astimezone(UTC)
    )

    assert service.get_system_timezone_name() == "UTC"


_JANUARY_NOON = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_JULY_NOON = datetime(2026, 7, 15, 12, 0, 0, tzinfo=UTC)


def _config(start: datetime, end: datetime) -> BacktestRunConfig:
    return BacktestRunConfig(
        strategy_key="ema_crossover",
        timeframe=TimeFrame.FIVE_MINUTES,
        initial_balance=10_000.0,
        start_time=start,
        end_time=end,
    )


@pytest.mark.parametrize(
    ("moment", "text"),
    [
        (_JANUARY_NOON, "2026-01-15 07:00:00 EST, UTC-05:00"),
        (_JULY_NOON, "2026-07-15 08:00:00 EDT, UTC-04:00"),
    ],
)
def test_a_text_names_the_offset_of_the_moment_it_shows_not_of_today(
    monkeypatch: pytest.MonkeyPatch, moment: datetime, text: str
) -> None:
    """`BUG-239`: the label came from `now`, so a January moment read on an October day
    claimed EDT. The machine is injected for every instant, "now" included."""
    monkeypatch.setattr(service, "machine_local_time", _machine_in("America/New_York"))

    assert zoned_moment_text(moment, service.SYSTEM_TIMEZONE_KEY) == text


def test_a_range_across_a_daylight_saving_change_names_each_bound_in_its_own_offset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "machine_local_time", _machine_in("America/New_York"))
    before = _config(_JANUARY_NOON, _JANUARY_NOON)
    after = _config(_JANUARY_NOON, _JULY_NOON)

    text = time_range_diff_text(before, after, service.SYSTEM_TIMEZONE_KEY)

    assert (
        text == "Time range (2026-01-15 07:00:00 EST, UTC-05:00.."
        "2026-01-15 07:00:00 EST, UTC-05:00 → 2026-01-15 07:00:00 EST, UTC-05:00.."
        "2026-07-15 08:00:00 EDT, UTC-04:00)"
    )


def test_a_range_inside_one_offset_names_the_zone_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "machine_local_time", _machine_in("America/New_York"))
    before = _config(_JANUARY_NOON, _JANUARY_NOON)
    after = _config(_JANUARY_NOON, datetime(2026, 2, 1, 12, 0, 0, tzinfo=UTC))

    text = time_range_diff_text(before, after, service.SYSTEM_TIMEZONE_KEY)

    assert text.endswith(" in EST, UTC-05:00")
    assert text.count("EST") == 1
