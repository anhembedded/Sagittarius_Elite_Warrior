# Standalone SymbolPicker

This component is application-neutral. It does not import `QmlOverlay`, the
application palette, an application ViewModel, an exchange client, or a
persistence store.

The host supplies two root properties:

- `vm`: a `SymbolPickerVM` (or another implementation of its abstract QML
  contract);
- `theme`: an object exposing the token properties used by `SymbolPicker.qml`.

Fallback objects are present only during initial scene construction, so the
component stays warning-free while a host attaches its real objects.

The file's root is a thin `Item` host — `QQuickWidget` requires an `Item` as
its root object, and `Popup` (the actual modal) is not one, so it can only be
declared as a child, never as the file's own root (`.agents/rules/qml-rule.md`
§0.1). The real modal is a `Popup` from `QtQuick.Controls`: its
`modal`/`closePolicy` properties supply the dim backdrop, Escape-to-close, and
click-outside-to-close, instead of this component hand-rolling them. The host
`Item` exposes `openPicker()`/`closePicker()`, which just open/close that
`Popup`. It can be placed inside any Qt Quick scene or hosted by any
`QQuickWidget` without an app-level modal wrapper.

`preview.py` is the local harness for `scripts/uml_preview.ps1`; it supplies a
small in-memory source and returns a `QQuickWidget` directly. It is preview
infrastructure only and is not imported by the component at runtime.

`SymbolPickerVM` owns two independent `SymbolListModel` instances. The QML
lists use `GridView(reuseItems: true)`, so 1000 symbols remain in the model but
only the visible cards are instantiated. Filtering is intentionally still a
linear `O(n)` scan in the VM. Each filter rebuild currently uses
`beginResetModel()`/`endResetModel()`, which may reset a view's scroll position;
row-level diffs can be introduced later if preserving that position becomes a
requirement.
