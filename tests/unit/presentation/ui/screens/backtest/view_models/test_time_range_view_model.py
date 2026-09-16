"""`EPIC-003F3` — `TimeRangeViewModel` on its own.

Constructed and asserted without `BackTestViewModel`: that a 1.400-line
facade is not needed to test five pieces of state is the whole point of
`EPIC-003`. The facade's forwarding is proven separately in
`../test_backtest_view_model_time_range_facade.py`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.time_range_preset import (
    TimeRangePreset,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.view_models.time_range_view_model import (
    TimeRangeViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    SYSTEM_TIMEZONE_KEY,
)


def test_defaults_to_all_history_and_the_default_timezone(qapp) -> None:
    vm = TimeRangeViewModel()

    assert vm.preset == TimeRangePreset.ALL_HISTORY.value
    assert vm.displayTimezone == DEFAULT_TIMEZONE
    assert vm.customStartText == ""
    assert vm.customEndText == ""


def test_every_preset_option_has_a_label_and_the_set_matches_the_enum(qapp) -> None:
    """A preset the enum knows about but the option list does not is
    unreachable from the UI, and one the list has but the enum does not
    resolves to no time range at all — both are silent."""
    vm = TimeRangeViewModel()

    values = [opt["value"] for opt in vm.presetOptions]

    assert set(values) == {member.value for member in TimeRangePreset}
    assert all(opt["label"] for opt in vm.presetOptions)


def test_selected_preset_label_follows_the_selected_preset(qapp) -> None:
    vm = TimeRangeViewModel()

    vm.preset = TimeRangePreset.LAST_7_DAYS.value

    assert vm.selectedPresetLabel == "Last 7 days"


def test_an_unknown_preset_shows_its_raw_value_rather_than_a_wrong_label(
    qapp,
) -> None:
    """Falling back to some default label would show the user a window the
    run does not actually cover."""
    vm = TimeRangeViewModel()

    vm.preset = "not_a_preset"

    assert vm.selectedPresetLabel == "not_a_preset"


def test_setting_the_same_value_twice_emits_once(qapp) -> None:
    vm = TimeRangeViewModel()
    seen: list[str] = []
    vm.presetChanged.connect(lambda: seen.append(vm.preset))
    vm.customStartTextChanged.connect(lambda: seen.append("start"))
    vm.displayTimezoneChanged.connect(lambda: seen.append("tz"))

    vm.preset = TimeRangePreset.CUSTOM.value
    vm.preset = TimeRangePreset.CUSTOM.value
    vm.customStartText = "2024-01-01 00:00"
    vm.customStartText = "2024-01-01 00:00"
    vm.set_display_timezone("Asia/Ho_Chi_Minh")
    vm.set_display_timezone("Asia/Ho_Chi_Minh")

    assert seen == [TimeRangePreset.CUSTOM.value, "start", "tz"]


def test_display_timezone_label_tracks_the_selected_timezone(qapp) -> None:
    """The label is `display_timezone_service`'s, not a second opinion:
    `UTC` for the default, `Hệ thống (...)` for the system key, and the
    IANA id itself for everything else."""
    vm = TimeRangeViewModel()
    assert vm.displayTimezoneLabel == "UTC"

    vm.set_display_timezone("Asia/Ho_Chi_Minh")
    assert vm.displayTimezoneLabel == "Asia/Ho_Chi_Minh"

    vm.set_display_timezone(SYSTEM_TIMEZONE_KEY)
    assert vm.displayTimezoneLabel.startswith("System (")


def test_the_timezone_the_label_lookup_uses_is_offered_by_the_options(qapp) -> None:
    """`backtest_state_fields.py` restores a saved timezone only if it is
    in `displayTimezoneOptions`; a default outside that list would be
    silently dropped on every restore."""
    vm = TimeRangeViewModel()

    assert DEFAULT_TIMEZONE in [opt["id"] for opt in vm.displayTimezoneOptions]
