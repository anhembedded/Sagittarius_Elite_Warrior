"""Capturing and restoring the Backtest form, as plain view-model transforms.

Lifted out of `BackTestPresenter` (`EPIC-003E` follow-up). Neither function
needs a presenter, a container or a view — only the view model — so pulling
them out makes the remembered-form logic testable on its own, which is the
part most worth testing and was previously reachable only by standing up a
whole presenter.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import StateData

from .backtest_state_fields import (
    BACKTEST_STATE_FIELDS,
    SCRIPTS_ENABLED_KEY,
    SCRIPTS_TOUCHED_KEY,
    is_key_list,
)


def capture(view_model) -> StateData:
    script_model = view_model.script_model
    return {
        **{
            field.key: getattr(view_model, field.prop)
            for field in BACKTEST_STATE_FIELDS
        },
        # EPIC-010G — the script checklist is a QAbstractListModel, not a
        # ViewModel property, so it cannot be a row in the table above. Two
        # keys, not one: remembering only which scripts are ON would let
        # `set_available()` re-apply a `default_enabled` over a script the
        # user deliberately turned off.
        SCRIPTS_ENABLED_KEY: list(script_model.enabled_keys),
        SCRIPTS_TOUCHED_KEY: list(script_model.touched_keys),
    }


def restore(view_model, data: StateData) -> None:
    """Applies a remembered form, validating every field on its own.

    D5, and boundary rule 4: the coordinator does not know what a valid
    leverage or commission type is, so the judgement lives here. Each field is
    applied independently — one corrupt value falls back alone rather than
    discarding the whole form.

    Writes the **ViewModel**, never a widget: several inputs on this screen are
    wired straight into handlers, and a restore must not look like the user
    typing (mode #12). Opening the screen still runs nothing.
    """
    for field in BACKTEST_STATE_FIELDS:
        if field.key not in data:
            continue
        value = data[field.key]
        if field.is_valid(value, view_model):
            setattr(view_model, field.prop, value)

    enabled = data.get(SCRIPTS_ENABLED_KEY)
    touched = data.get(SCRIPTS_TOUCHED_KEY)
    if is_key_list(enabled) and is_key_list(touched):
        # Both or neither: applying `enabled` without `touched` would leave
        # every key looking untouched, so the next `set_available()` would
        # switch the defaults straight back on.
        view_model.script_model.restore_selection(enabled, touched)
