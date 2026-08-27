"""Capture/restore of the remembered Backtest form — no presenter involved.

That is the point of pulling these out: the remembered-form logic is the part
most worth testing, and it was previously reachable only by standing up a
whole `BackTestPresenter` behind mocks.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_state_fields import (
    BACKTEST_STATE_FIELDS,
    SCRIPTS_ENABLED_KEY,
    SCRIPTS_TOUCHED_KEY,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.state_persistence import (
    capture,
    restore,
)


def test_capture_records_every_declared_field(qtbot) -> None:
    """Driven off `BACKTEST_STATE_FIELDS`, so a field added to the table but
    not to the capture would be a silently forgotten setting."""
    captured = capture(BackTestViewModel())

    for field in BACKTEST_STATE_FIELDS:
        assert field.key in captured, f"{field.key} not captured"


def test_capture_records_the_script_checklist_as_two_keys(qtbot) -> None:
    """EPIC-010G: remembering only which scripts are ON would let
    `set_available()` re-apply a default over one the user turned off."""
    captured = capture(BackTestViewModel())

    assert SCRIPTS_ENABLED_KEY in captured
    assert SCRIPTS_TOUCHED_KEY in captured


def test_a_captured_form_restores_onto_a_fresh_view_model(qtbot) -> None:
    source = BackTestViewModel()
    source.selectedTimeframe = "15m"
    source.initialCapitalText = "12345"

    target = BackTestViewModel()
    restore(target, capture(source))

    assert target.selectedTimeframe == "15m"
    assert target.initialCapitalText == "12345"


def test_one_corrupt_value_falls_back_alone(qtbot) -> None:
    """Boundary rule 4: each field is validated on its own, so a single bad
    value must not discard the rest of the remembered form."""
    view_model = BackTestViewModel()
    good = capture(view_model)
    # Keys, not property names: the table maps `capital` -> `initialCapitalText`.
    good["timeframe"] = "not-a-timeframe"
    good["capital"] = "999"

    restore(view_model, good)

    assert view_model.selectedTimeframe != "not-a-timeframe"
    assert view_model.initialCapitalText == "999"


def test_a_missing_key_is_skipped_rather_than_written_as_none(qtbot) -> None:
    """An older remembered form simply lacks a newer field."""
    view_model = BackTestViewModel()
    before = view_model.selectedTimeframe

    restore(view_model, {"capital": "777"})

    assert view_model.selectedTimeframe == before
    assert view_model.initialCapitalText == "777"


def test_the_script_checklist_needs_both_keys_or_neither(qtbot) -> None:
    """Applying `enabled` without `touched` leaves every key looking
    untouched, so the next `set_available()` switches the defaults back on."""
    view_model = BackTestViewModel()
    restored: list[tuple] = []
    view_model.script_model.restore_selection = lambda e, t: restored.append((e, t))

    restore(view_model, {SCRIPTS_ENABLED_KEY: ["ema"]})
    assert restored == []

    restore(view_model, {SCRIPTS_ENABLED_KEY: ["ema"], SCRIPTS_TOUCHED_KEY: ["ema"]})
    assert restored == [(["ema"], ["ema"])]
