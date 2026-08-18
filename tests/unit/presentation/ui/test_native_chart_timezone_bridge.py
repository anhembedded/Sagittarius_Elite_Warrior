from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_timezone_bridge import (
    NativeChartTimezoneBridge,
)

#: 2024-01-01 00:00:00 UTC
_TIMESTAMP_UTC_MS = 1_704_067_200_000


def test_format_timestamp_defaults_to_utc(qapp):
    bridge = NativeChartTimezoneBridge()
    assert bridge.formatTimestamp(_TIMESTAMP_UTC_MS, "UTC") == "2024-01-01 00:00:00"


def test_format_timestamp_converts_to_the_selected_zone(qapp):
    bridge = NativeChartTimezoneBridge()
    # Asia/Ho_Chi_Minh is UTC+7, no DST.
    assert (
        bridge.formatTimestamp(_TIMESTAMP_UTC_MS, "Asia/Ho_Chi_Minh")
        == "2024-01-01 07:00:00"
    )


def test_format_timestamp_falls_back_to_utc_for_an_unresolvable_zone(qapp):
    bridge = NativeChartTimezoneBridge()
    assert (
        bridge.formatTimestamp(_TIMESTAMP_UTC_MS, "Not/ARealZone")
        == "2024-01-01 00:00:00"
    )


def test_format_axis_time_is_hour_minute_only(qapp):
    bridge = NativeChartTimezoneBridge()
    assert bridge.formatAxisTime(_TIMESTAMP_UTC_MS, "UTC") == "00:00"
    assert bridge.formatAxisTime(_TIMESTAMP_UTC_MS, "Asia/Ho_Chi_Minh") == "07:00"
