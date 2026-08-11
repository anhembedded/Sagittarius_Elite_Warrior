"""Tests for IndicatorScriptListModel (BOT-032 Phase 3)."""

from PySide6.QtCore import QModelIndex

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.indicator_script_list_model import (
    IndicatorScriptListModel,
)


class _FakeScript:
    title = "EMA Ribbon"


class _FakeScriptNoTitle:
    pass


class _FakeDefaultOnScript:
    title = "EMA 20"
    default_enabled = True


def test_set_available_populates_rows_in_registration_order(qapp):
    model = IndicatorScriptListModel()

    model.set_available({"ema_ribbon": _FakeScript, "ema_cross": _FakeScript})

    assert model.rowCount() == 2
    first = model.index(0, 0)
    assert model.data(first, IndicatorScriptListModel.KeyRole) == "ema_ribbon"
    assert model.data(first, IndicatorScriptListModel.TitleRole) == "EMA Ribbon"


def test_a_script_with_no_title_attribute_falls_back_to_its_key(qapp):
    model = IndicatorScriptListModel()

    model.set_available({"mystery": _FakeScriptNoTitle})

    index = model.index(0, 0)
    assert model.data(index, IndicatorScriptListModel.TitleRole) == "mystery"


def test_rows_start_disabled(qapp):
    model = IndicatorScriptListModel()
    model.set_available({"ema_ribbon": _FakeScript})

    index = model.index(0, 0)
    assert model.data(index, IndicatorScriptListModel.EnabledRole) is False
    assert model.enabled_keys == []


def test_set_enabled_toggles_a_row_and_updates_enabled_keys(qapp):
    model = IndicatorScriptListModel()
    model.set_available({"ema_ribbon": _FakeScript, "ema_cross": _FakeScript})

    model.setEnabled(1, True)

    assert model.enabled_keys == ["ema_cross"]
    index = model.index(1, 0)
    assert model.data(index, IndicatorScriptListModel.EnabledRole) is True


def test_set_enabled_false_removes_it_again(qapp):
    model = IndicatorScriptListModel()
    model.set_available({"ema_ribbon": _FakeScript})
    model.setEnabled(0, True)

    model.setEnabled(0, False)

    assert model.enabled_keys == []


def test_set_enabled_out_of_range_row_is_a_no_op(qapp):
    model = IndicatorScriptListModel()
    model.set_available({"ema_ribbon": _FakeScript})

    model.setEnabled(5, True)  # must not raise

    assert model.enabled_keys == []


def test_re_calling_set_available_keeps_enabled_state_for_surviving_keys(qapp):
    model = IndicatorScriptListModel()
    model.set_available({"ema_ribbon": _FakeScript, "ema_cross": _FakeScript})
    model.setEnabled(0, True)  # ema_ribbon

    model.set_available({"ema_ribbon": _FakeScript, "macd_full": _FakeScript})

    assert model.enabled_keys == ["ema_ribbon"]


def test_re_calling_set_available_drops_enabled_state_for_removed_keys(qapp):
    """A key that vanished (script unregistered) must not leak into
    enabled_keys forever — that would silently re-enable a script the next
    time it happened to be re-registered under the same key."""
    model = IndicatorScriptListModel()
    model.set_available({"ema_ribbon": _FakeScript})
    model.setEnabled(0, True)

    model.set_available({"macd_full": _FakeScript})

    assert model.enabled_keys == []


def test_enabled_keys_order_matches_registration_order_not_toggle_order(qapp):
    model = IndicatorScriptListModel()
    model.set_available(
        {"ema_ribbon": _FakeScript, "ema_cross": _FakeScript, "macd_full": _FakeScript}
    )

    model.setEnabled(2, True)  # macd_full toggled first
    model.setEnabled(0, True)  # ema_ribbon toggled second

    assert model.enabled_keys == ["ema_ribbon", "macd_full"]


def test_data_returns_none_for_an_invalid_index(qapp):
    model = IndicatorScriptListModel()
    model.set_available({"ema_ribbon": _FakeScript})

    assert model.data(QModelIndex()) is None


# ---------------------------------------------------------------------------
# default_enabled (BOT-032 Phase 6)
# ---------------------------------------------------------------------------


def test_a_default_enabled_script_starts_on(qapp):
    model = IndicatorScriptListModel()

    model.set_available({"ema_20": _FakeDefaultOnScript})

    assert model.enabled_keys == ["ema_20"]


def test_a_script_without_default_enabled_still_starts_off(qapp):
    model = IndicatorScriptListModel()

    model.set_available({"ema_ribbon": _FakeScript, "ema_20": _FakeDefaultOnScript})

    assert model.enabled_keys == ["ema_20"]


def test_turning_off_a_default_enabled_script_sticks_across_a_reload(qapp):
    """set_available() re-applying its own default would make the checkbox
    un-uncheckable — the user's manual choice must win."""
    model = IndicatorScriptListModel()
    model.set_available({"ema_20": _FakeDefaultOnScript})
    model.setEnabled(0, False)

    model.set_available({"ema_20": _FakeDefaultOnScript})

    assert model.enabled_keys == []


def test_turning_on_a_normally_off_script_also_sticks_across_a_reload(qapp):
    model = IndicatorScriptListModel()
    model.set_available({"ema_ribbon": _FakeScript})
    model.setEnabled(0, True)

    model.set_available({"ema_ribbon": _FakeScript})

    assert model.enabled_keys == ["ema_ribbon"]
