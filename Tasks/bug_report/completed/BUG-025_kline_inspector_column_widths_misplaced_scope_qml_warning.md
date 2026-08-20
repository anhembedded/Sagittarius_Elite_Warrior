# BUG-025 — KLineInspectorModal emits "Unable to assign [undefined] to double" QML warnings on open because column widths are declared inside ColumnLayout instead of the modal root

**Reported:** 2026-08-21, user opened the Database (Storage Vault) screen in dev mode and observed QML binding evaluation warnings on loading `data_management`:
`KLineInspectorModal.qml:173:148: Unable to assign [undefined] to double` across all header and delegate column width bindings.
**Severity:** P3 — No visual crash, but `root.colTimeWidth`, `root.colPriceWidth`, `root.colVolWidth`, `root.colChangeWidth`, and `root.colTradesWidth` evaluate to `undefined`, polluting the dev session log and failing the zero-QML-warning contract.
**Status:** ✅ Fixed 2026-08-21 — root-caused, reproduced with failing regression test, and fixed by moving column width properties to modal root scope.

## Symptom

```text
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:173:148: Unable to assign [undefined] to double
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:173:106: Unable to assign [undefined] to double
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:174:143: Unable to assign [undefined] to double
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:174:100: Unable to assign [undefined] to double
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:175:144: Unable to assign [undefined] to double
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:175:101: Unable to assign [undefined] to double
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:176:144: Unable to assign [undefined] to double
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:176:101: Unable to assign [undefined] to double
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:177:146: Unable to assign [undefined] to double
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:177:103: Unable to assign [undefined] to double
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:178:148: Unable to assign [undefined] to double
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:178:107: Unable to assign [undefined] to double
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:179:144: Unable to assign [undefined] to double
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:179:100: Unable to assign [undefined] to double
file:///.../src/presentation/ui/screens/data_management/KLineInspectorModal.qml:180:122: Unable to assign [undefined] to double
```

## Root Cause

In `src/presentation/ui/screens/data_management/KLineInspectorModal.qml`:
`ModalDialogCard` is declared with `id: root`.
At lines 152–156, the column width properties:
```qml
readonly property real colTimeWidth: 140
readonly property real colPriceWidth: 80
readonly property real colVolWidth: 105
readonly property real colChangeWidth: 75
readonly property real colTradesWidth: 70
```
were declared inside the inner `ColumnLayout` (lines 21–406), not on `root` (`ModalDialogCard`).
When the header `RowLayout` (lines 173–180) and row delegate `RowLayout` (lines 205–260) bind to `root.colTimeWidth`, `root.colPriceWidth`, etc., QML looks for these properties on `root`, finds `undefined`, and raises runtime type coercion warnings when assigning `undefined` to `Layout.preferredWidth` / `Layout.minimumWidth` (which expect type `double`).

## Fix

Moved the 5 `readonly property real col*Width` declarations to the top-level `ModalDialogCard` (`root`) scope alongside `preferredWidth` and `preferredHeight`.

## Regression Test

`tests/unit/presentation/ui/screens/test_kline_inspector_modal_qml.py` proves:
1. `root.colTimeWidth`, `root.colPriceWidth`, `root.colVolWidth`, `root.colChangeWidth`, and `root.colTradesWidth` resolve to positive floats on the modal's root object (`140.0`, `80.0`, `105.0`, `75.0`, `70.0`).
2. QML construction produces zero warning messages and no `Unable to assign [undefined] to double` errors.
3. Test confirmed failing before the fix (with exact `Unable to assign [undefined] to double` Qt messages) and passing green (100%) after the fix.
