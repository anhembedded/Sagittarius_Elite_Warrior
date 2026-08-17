# BOT-095E — QML Rule Audit

**Date:** 2026-08-17  
**Scope:** `BotParamsDialog.qml`, `BotParamField.qml`, and `CapitalDialog.qml` changes made for BOT-095E real-time validation and parameter step metadata.

## Result

The feature follows the important user-facing contracts: validation is surfaced through the ViewModel, controls expose stable automation names, and the dynamic validation message is rendered as plain text. The audit found two architectural violations during implementation; both were resolved before verification.

## Passed / corrected in this audit

- Commands route from QML into ViewModel slots; capital validity is owned by the Presenter/ViewModel rather than a QML-only error state.
- `btnResetBotParams`, cancel/apply/save controls, and dynamic parameter fields have stable `objectName` values for automated interaction.
- The external/dynamic parameter label and capital validation message use `Text.PlainText`.
- The newly-added error colour uses the existing `Theme.danger` semantic token.
- All three dialogs use responsive popup sizing and clipped scrolling where a scrolling form is present.

## Resolved findings

### BOT-095E3 — expose an immutable parameter-row presentation model

`BotParamsDialog.qml` had flattened `botParamsSchema` into `ListModel` with `reloadParameterRows()`. This was data transformation in QML and introduced sentinel bounds and duplicated schema semantics. It now receives ready-to-render `botParamsRows`, built by `build_bot_params_rows()` in Python and exposed from the ViewModel. QML only repeats those rows.

### BOT-095E4 — move numeric stepping rules behind the ViewModel

`BotParamField.qml` had calculated numeric step, precision, bounds, and next value in JavaScript. The `step_numeric_param_value()` Python rule now owns Decimal-safe stepping and clamping; QML forwards the field name/current text/direction to `step_bot_param_value()` and only applies the returned text.

### Test gap — resolved interaction coverage

The popup test now opens the real overlay dialog, focuses `fldBotParam_period`, sends a real Qt `↑` event, and proves the visible text changes from `20` to `21` via the ViewModel/Python normalizer. `Popup` itself is reached through the real overlay root's `findChild()` because Qt detaches it from the visual `childItems()` tree. Desktop E2E remains opt-in for native input/render validation.

## Deliberate non-findings

- `BotParamsDialog.qml` is 241 lines and `BotParamField.qml` is 206 lines: both are below the 300-line review threshold.
- No animation is required for these form controls. Adding it without an interaction benchmark would be counterproductive while BOT-098 investigates chart responsiveness.
- Existing literal fallback palette values in shared/legacy components are a migration concern. This audit does not broaden BOT-095E into a repository-wide visual-token migration.
