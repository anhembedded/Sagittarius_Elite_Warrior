"""`EPIC-010G` — a script the user switched off stays off across a restart.

@par The defect this closes
`IndicatorScriptListModel` already tracks `_user_touched` so that
`set_available()` applies a script's `default_enabled` only the first time that
script is seen, never over a choice the user already made. But that set lives
only in memory. After a restart it is empty again, so a `default_enabled`
script the user deliberately turned off is switched straight back on — the
setting looks like it did not stick.

Remembering only *which scripts are on* does not fix it: the next
`set_available()` sees an untouched key and re-applies the default. Both sets
have to survive together, which is why the slice carries two keys.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.components.indicator_scripts.list_model import (
    IndicatorScriptListModel,
)


class _PlainScript:
    title = "Plain"


class _DefaultOnScript:
    title = "Default On"
    default_enabled = True


@pytest.fixture
def available():
    return {"plain": _PlainScript, "default_on": _DefaultOnScript}


@pytest.fixture
def model(qapp, available):
    m = IndicatorScriptListModel()
    m.set_available(available)
    return m


def _row_of(model: IndicatorScriptListModel, key: str) -> int:
    return next(
        row
        for row in range(model.rowCount())
        if model.data(model.index(row, 0), IndicatorScriptListModel.KeyRole) == key
    )


def test_a_default_on_script_starts_enabled(model):
    """The behaviour being protected, stated first so the regression below is
    unambiguous: a fresh install really does switch this script on."""
    assert model.enabled_keys == ["default_on"]
    assert model.touched_keys == []


def test_turning_a_default_on_script_off_marks_it_touched(model):
    model.setEnabled(_row_of(model, "default_on"), False)

    assert model.enabled_keys == []
    assert model.touched_keys == ["default_on"]


def test_a_script_turned_off_stays_off_after_a_restart(qapp, available, model):
    """The regression itself. `reopened` is a fresh model over the same
    scripts, as a real relaunch would be."""
    model.setEnabled(_row_of(model, "default_on"), False)
    remembered_enabled = list(model.enabled_keys)
    remembered_touched = list(model.touched_keys)

    reopened = IndicatorScriptListModel()
    reopened.set_available(available)
    reopened.restore_selection(remembered_enabled, remembered_touched)

    assert reopened.enabled_keys == []


def test_the_choice_survives_a_second_restart_too(qapp, available, model):
    """One restart is not enough to prove this works.

    A restored model must re-export the touched set, not just consume it —
    otherwise launch 2 looks correct while launch 3 quietly switches the
    script back on, because `set_available()` sees an untouched key again.
    Written after fault injection showed the single-restart tests below all
    still passing with `_user_touched` deliberately dropped on restore.
    """
    model.setEnabled(_row_of(model, "default_on"), False)

    launch_2 = IndicatorScriptListModel()
    launch_2.set_available(available)
    launch_2.restore_selection(model.enabled_keys, model.touched_keys)

    launch_3 = IndicatorScriptListModel()
    launch_3.set_available(available)
    launch_3.restore_selection(launch_2.enabled_keys, launch_2.touched_keys)

    assert launch_3.enabled_keys == [], (
        "the touched set must survive being restored, not just being written"
    )


def test_remembering_only_the_enabled_set_would_not_have_been_enough(
    qapp, available, model
):
    """Pins *why* the slice carries two keys rather than one, so a later
    simplification to a single list fails here instead of silently
    reintroducing the bug."""
    model.setEnabled(_row_of(model, "default_on"), False)

    reopened = IndicatorScriptListModel()
    reopened.set_available(available)
    reopened.restore_selection(model.enabled_keys, touched=[])  # the naive version

    assert reopened.enabled_keys == ["default_on"], (
        "without the touched set, set_available() re-applies default_enabled"
    )


def test_a_new_default_on_script_still_arrives_switched_on(qapp, model):
    """The other direction, and the reason `restore_selection()` layers rather
    than replaces: a `default_enabled` script shipped in a later release did
    not exist when the slice was written, so it appears in neither remembered
    set. It must still come on — an existing user should not silently miss a
    new default just because they have a saved selection."""
    model.setEnabled(_row_of(model, "plain"), True)
    remembered_enabled = list(model.enabled_keys)
    remembered_touched = list(model.touched_keys)

    class _NewDefaultOnScript:
        title = "Added Later"
        default_enabled = True

    reopened = IndicatorScriptListModel()
    reopened.set_available(
        {
            "plain": _PlainScript,
            "default_on": _DefaultOnScript,
            "added_later": _NewDefaultOnScript,
        }
    )
    reopened.restore_selection(remembered_enabled, remembered_touched)

    assert "added_later" in reopened.enabled_keys


def test_a_script_the_user_switched_on_comes_back_on(qapp, available, model):
    model.setEnabled(_row_of(model, "plain"), True)

    reopened = IndicatorScriptListModel()
    reopened.set_available(available)
    reopened.restore_selection(model.enabled_keys, model.touched_keys)

    assert "plain" in reopened.enabled_keys


def test_a_script_that_no_longer_exists_is_dropped(qapp, available):
    """Same rule `set_available()` already enforces: a stale key must not
    leak into `enabled_keys` forever."""
    model = IndicatorScriptListModel()
    model.set_available(available)

    model.restore_selection(["plain", "deleted_script"], ["plain", "deleted_script"])

    assert "deleted_script" not in model.enabled_keys
    assert "deleted_script" not in model.touched_keys


def test_restoring_into_an_empty_registry_does_not_raise(qapp):
    model = IndicatorScriptListModel()
    model.set_available({})

    model.restore_selection(["anything"], ["anything"])

    assert model.enabled_keys == []


def test_touched_keys_are_sorted_so_the_slice_is_stable(model):
    """Two runs that changed nothing must produce byte-identical output —
    otherwise the debounce writes a "new" value on every launch."""
    model.setEnabled(_row_of(model, "plain"), True)
    model.setEnabled(_row_of(model, "default_on"), False)

    assert model.touched_keys == sorted(model.touched_keys)
