---
name: QML Widget Rule
description: QML lives in exactly one place — individual widgets embedded via QQuickWidget, not the shell and not the chart. The 1 widget = 1 directory (.qml + _vm.py) architecture, when to skip a dedicated ViewModel, style tokens mandatory from day one, and the Qt Quick gotchas actually measured here (Repeater takes 1 delegate, full rebuild, findChild cannot reach).
trigger: on_file_change
patterns:
  - "**/*.qml"
  - src/presentation/ui/qml/**/*.py
---

# 🎨 QML WIDGET STANDARDS

This file holds only the **standard architecture — how to build, not how far the build has
got**; the roadmap/progress lives in
[`EPIC-015`](../../Tasks/epics/EPIC-015_qml_tung_widget_khong_chuyen_chart/README.md).

## 0. The root constraint — it decides everything else in this file

**QML can be nested inside QtWidgets. Qt does not support the reverse.** The chart is pyqtgraph
(`QGraphicsView`, pure QtWidgets) — therefore:

- **Shell** (`main_window.py`, `QStackedWidget`, `Sidebar`) — **QtWidgets forever**.
- **Chart** (`src/presentation/ui/components/chart_card/`) — **QtWidgets forever**, because of the
  nesting constraint: whatever contains the chart must be QtWidgets (not for performance reasons).
- **Everything else** — an individual widget (modal, panel, picker, form field) **may** be built in
  QML and embedded inside a QtWidgets chrome via `QQuickWidget`.

QtWidgets is the app-wide default; QML is **opt-in per widget**, decided per §2. Three nesting
patterns have been measured to actually work (`EPIC-015` spikes A/B/C):

| Pattern | Who contains whom | Example in this repo |
| :--- | :--- | :--- |
| QML panel next to the chart | `QVBoxLayout` (widget) holds both a `QQuickWidget` and a `ChartCard` | not used yet |
| A whole route in QML | `QStackedWidget` holds one `QQuickWidget` as the entire screen | not used yet — Settings/Data Management |
| QML modal | `QDialog`/`Overlay` holds a `QQuickWidget` as its body | `QmlOverlay` (`src/presentation/ui/qml/host.py`) — in use |

### 0.1 QML modals — two shapes, not one

The technical reason (measured from Qt itself): `QtQuick.Controls`' `Popup`/`Dialog` dims and
blocks interaction through the `Overlay.overlay` attached to the **`Window`** that contains it, and
a `QQuickWidget` is its own Qt Quick window, separate from the QtWidgets widgets sitting next to
it — so a `Popup` opened inside a small `QQuickWidget` **cannot** cover the surrounding QtWidgets,
and reports no error at all.

| What the host is | The right approach | Why |
| :--- | :--- | :--- |
| The route/screen is still QtWidgets (most screens today) | `QmlOverlay` (a real QtWidgets `QDialog` holding a QML body) | Only a real `QDialog` can dim and block the whole app while the rest is QtWidgets. The `.qml` inside is **only the body layout** (`Column`/`Grid`/`ScrollView` — see `SelectList`/`CheckboxList`/`StatGrid`/`Capital`); it does not build a modal of its own. |
| The route/screen is already entirely QML | A native `QtQuick.Controls` `Popup`/`Dialog` as the root of the modal component | The whole route is a single `QQuickWindow`, so the `Popup` dims the full screen correctly. Use `Popup`/`Dialog` instead of hand-rolling `Item` + backdrop + manual key handling — they give you Escape-to-close, `closePolicy` and a focus scope for free; rewriting that duplicates an already-tested Qt surface. |

`SymbolPicker.qml` falls into the second row but hand-rolls `Item` + backdrop + keyboard — §9.

### 0.2 `src/presentation/ui/qml/` is the official place to build QML components

- **If it can be shared, build it shared — do not write a "nearly identical" copy.** Before
  creating a new `.qml`, check the shape table in §2 and the VMs that already exist (`SelectList`,
  `StatGrid`, `CheckboxList`, `TimeRangePicker`, ...). A shape that is "almost the same but a bit
  different" is a signal to **generalise** an existing component (add a flag, add a callback) —
  the way `SelectListVM` absorbed `TimezonePickerVM` and the original was deleted rather than kept
  as a forwarder — not a signal to write a new widget in parallel.
- **Adding a feature to an existing widget: first ask whether the current design still holds.** If
  it does not, change the design (change the VM contract, change how the interface splits
  read/write, re-split the component) — **no hotfix, and no keeping the old design and bolting on
  an `if is_special_case:` branch**. Example: `ISymbolPickerSource` had only `get_*` until
  `toggleFavourite()` needed to write; the contract gained `set_favourite()` so read and write are
  symmetric.
- **Prefer the design patterns already in this file** — explicit Port/interface
  (`architecture-rule.md`, implicit duck-typing forbidden), callback-constructed VMs (§1.1), VMs
  holding all state and rules (§1.2), the modal shape that matches the host (§0.1) — over a
  bespoke approach per widget.

## 1. Architecture: 1 QML widget = 1 directory

```
src/presentation/ui/qml/
  host.py                  QmlOverlay — QtWidgets chrome, QML body
  <Widget>/
    <Widget>.qml           layout + bindings only, NO logic
    <widget>_vm.py         all state + rules, NO QML imports
    NOTES.md               why this widget exists, who uses it
```

`.qml` and `_vm.py` **sit side by side in the same directory** — Single-Scope Cohesion
(`code-quality-rule.md` §4): splitting the shell and the state into two distant places is exactly
how they drift apart. Live examples: `SelectList/`, `CheckboxList/`, `StatGrid/`, `Capital/`.

### 1.1 Widget ViewModel: who creates it, who holds it

**Python (the parent screen) creates the ViewModel and injects it into the `.qml` via the `vm`
context property.** A `.qml` file **never** instantiates its own backend (§5.1) —
construction/injection belongs in the composition root, where it is testable with mocks/callbacks
without standing up QML.

```python
# dialog/panel Python — composition root; callbacks read live from the screen VM
self._widget_vm = SelectListVM(get_options=lambda: view_model.strategyOptions,
                               get_current=lambda: view_model.selectedStrategyKey)
super().__init__(..., qml_file=_QML, context={"vm": self._widget_vm})
# .qml only reads, never computes:   Text { text: vm.rows[0].label }
```

### 1.2 The widget ViewModel holds ALL state and rules

| Layer | Contains | Tested with |
| :--- | :--- | :--- |
| `<Widget>.qml` | Layout, bindings, animation only | Render smoke test (few, cheap) |
| `<widget>_vm.py` | Filtering, computing `selected`, validation, formatting | **Plain pytest, with `QApplication.instance()` being `None` throughout the test** |

Actually measured: 16 `SelectListVM`/`CheckboxListVM`/`StatGridVM` tests run in **0.6 seconds, with
no `QApplication` and no QML**. Hard rule: **no `if`/loops/computation in `.qml`** — a single
binding expression is fine (`visible: modelData.subtitle !== ""`), two or more lines of JavaScript
belong in `_vm.py`.

### 1.3 When a dedicated widget ViewModel is **NOT** needed

> User decision 2026-08-28: *"for UIs where the viewmodel adds nothing, just a 1:1 forward, no
> viewmodel is needed."*

This applies `architecture-rule.md` §7.2 (*"Abstraction does not mean spawning an extra
intermediate layer for its own sake"*): a widget VM whose entire body is `return
self._screen_vm.x` is not a contract — it is a second copy of state that already exists, exactly
the shape of the `BUG-064` defect: two places holding the same truth, with nothing forcing them to
match. **Ask in this order:**

1. **Shared across ≥1 different screens?** (`SelectList`/`CheckboxList`/`StatGrid`) → **always give
   it its own VM**, constructed with callbacks (`get_options`, `get_rows`, ...), regardless of
   whether one specific call site looks "1:1": the contract ("hand me a list in the shape
   `{id, label, ...}`") **is** the value — it decouples the widget from every screen's ViewModel.
   `StatGridVM` only uppercases the title and maps `Tone` → string, and is still kept.
2. **Used by exactly one screen?** Does the `.qml` need a **derived value** that is not already on
   that screen's ViewModel (`selected` computed from a comparison, `canApply` computed from
   validation, string formatting, merged properties)? **Yes** → give it its own VM (`CapitalVM`:
   `canApply` is derived, not a copy). **No, it only reads/writes existing properties directly** →
   **drop the dedicated VM**, inject the screen ViewModel straight in
   (`context={"vm": view_model}`) and let the `.qml` bind directly to `vm.someScreenProperty`.
3. Do you need to **hide part of** the screen ViewModel's surface (a screen with 40 unrelated
   properties — exposing all of them leaks encapsulation)? → give it its own VM even if it
   transforms nothing, purely to bound the API.

No current widget violates this — the rule applies **from now on**.

### 1.4 "Widget" here means a Qt `Component`

[`QML Component type`](https://doc.qt.io/qt-6/qml-qtqml-component.html): a `.qml` file whose name
is **capitalised** automatically becomes a reusable Component type via `import`; a **lowercase**
name is not registered as a type by Qt (loading it by direct path works, `import` does not) —
**keep the capitalisation convention**. The inline `Component { ... }` form is lazy/deferred
instantiation (`Repeater`/`ListView` delegates, a `Loader`'s `sourceComponent`) — the common root
of §4.2 and the `Loader` recommendation in §6.6.

## 2. When to choose QML for a new widget

QML is not the default for a whole screen. Choose QML for **one specific widget** when: it matches
a shape that already has a shared component (table below — reuse it, do not write a new `.qml`); it
belongs to a screen `EPIC-015` is currently migrating; or it is handed an image mockup directly and
the speed of translating mockup → code outweighs the cost of two styling pipelines (the original
`BOT-030` rationale, still valid — see
[`ASSESSMENT_2026-08-28_qtwidgets_sang_qml.md`](../../Tasks/reports/ASSESSMENT_2026-08-28_qtwidgets_sang_qml.md)).

**Existing shared components — check these before writing a new `.qml`:**

| Shape | Component | Use when |
| :--- | :--- | :--- |
| Pick one from a list | `SelectList` | `Repeater`, click → emit → close |
| Read-only list | `SelectList` (`selectable=False`) | same model, click removed |
| Read-only card grid | `StatGrid` | non-interactive, numbers only |
| Multi-select checkboxes | `CheckboxList` | rows independent; any locking/exclusion rules live in the dialog, not the VM |
| Form with validation | hand-written, following `Capital` | fields and validation results must stay in sync |

## 3. Style — mandatory from day one, even when "no design is needed yet"

> User 2026-08-28: *"we should drop styling, no need to style this early."* Correct for the
> **design** part (no kit, no new tokens, no pixel-chasing). **Wrong if applied to using tokens —
> that is not styling, that is the correct baseline.**

The measured reasons: (1) **"no style" means a white box on a black background** — a default
QtQuick Controls button is `#f5f5f5` on the app's `#0a0a0c` background; (2) **the native Windows
style ignores `background:` without reporting an error**, it only logs a warning and then draws
the default chrome, so deferring styling defers discovering the trap until the worst possible
moment (the user's machine); (3) this repo has caught the "every widget paints itself" disease
twice already (`EPIC-005` left 8 separate `setStyleSheet` calls; `EPIC-006B` had to clean them up).
**Mandatory for every new `.qml`, no "later":**

- Call `ensure_qml_style()` (pinning the `"Basic"` style) inside `QmlOverlay.__init__`/the shared
  host, **not only at app bootstrap**: tests construct dialogs directly without going through the
  bootstrapper, so pinning only at bootstrap makes tests pass on native chrome that users never see.
- Every colour **must** be a `Theme.<token>` (`register_theme()` installs the `Theme` context
  property). **Hex literals (`"#..."`) and literal colour names (except `"transparent"`) are
  forbidden in `.qml`** — the guard already exists, see `test_qml_style_discipline.py`; it mirrors
  the widget-side hex-literal guard (`kit/guards.py`).
- Verify a token actually exists before using it, do not guess the name — `Tone.POSITIVE` maps to
  `Theme.success`, not `Theme.positive` (check with `Palette.as_ui_dict()` before shipping).

**Design** work (spacing scale, animation, elevation) can still be deferred; **using tokens instead
of literals** cannot, because fixing it later is more expensive (one `sed` across the app versus
combing through every file).

## 4. Qt Quick gotchas — actually measured, not speculation

These four **do not surface as compile errors or warnings** — `ruff`/`mypy` do not read `.qml`, and
Qt Quick stays silent when you use it wrong.

### 4.1 A `Repeater` accepts exactly ONE delegate

Putting two `Item`s (e.g. a `Rectangle` for the selectable shape plus a `Row` for the read-only
shape) as **direct siblings** inside a `Repeater` → only the last one is created, the other is
**never instantiated**, with no error and no warning. Fix: wrap both in **a single parent `Item`**
per index.

### 4.2 `Repeater { model: <list of dicts/QVariantList> }` destroys and recreates EVERY delegate on every model change

Even when only one element changed. Measured by holding a Python reference to one delegate across
two consecutive `rowsChanged.emit()` calls — the id changes entirely, and the old item is a dead
object. **Never hold a delegate reference across a refresh**; look it up again after every
`rowsChanged`/`optionsChanged`/`cardsChanged`. This is also the performance rationale behind the
model-view rule in §6.6: a small static list can use a `Repeater`, but a large or continuously
updating list must be wrapped in a `QAbstractListModel` (Python) — that one emits `dataChanged` per
row instead of rebuilding the whole block.

### 4.3 `findChild` CANNOT reach items created by a `Repeater`

Use `qml_item`/`find_qml_item` from `tests/conftest.py` (they walk `childItems()`; original note:
*"verified empirically while building the QML sidebar"*), and do not rewrite them —
`find_qml_item` is the one canonical name, and `find_all_named` (prefix matching for `Repeater`
rows) lives alongside it there. `findChild` is still correct for statically declared items and for
the `Popup` boundary (which is detached from `childItems()` in the other direction).

### 4.4 QtQuick Controls signal signatures differ from the equivalent widget

`TextField.textEdited` **takes no parameters**; `QLineEdit.textEdited(str)` (the widget) does.
Faking a signal by hand (`QMetaObject.invokeMethod` with the wrong parameter count) fails
**silently** or raises a baffling error. Use `QTest.keyClicks`/`QTest.mouseClick` to simulate the
real action instead of guessing the signature.

## 5. 🧩 Code Practices in `.qml`

- **5.1 Strict separation of UI and business logic.** QML files define only visual layout, theme bindings, micro-animations, and user-interaction signals. Move all calculations, data transformations, domain validation, and state machines into the widget's `_vm.py` (§1) or the screen's `Presenter`/`ViewModel`/`Domain`; small view-local helpers (focus handling, invoking a slot, resetting an already-rendered input) are permitted only when they do not duplicate a business rule or become a second source of state. UI triggers actions by invoking `vm` slots/methods — one-way command dispatch; the Presenter/coordinator runs the logic and updates ViewModel properties.
- **5.2 Reactive bindings over manual assignment.** Always bind QML element properties directly to `vm` properties or `Theme`. Never break bindings with imperative assignments inside signal handlers.
- **5.3 Component modularization & SRP.** Treat **300 lines** as a mandatory review threshold (not a blind line-count failure) for breaking up a god component: shared widget shapes (`SelectList.qml`, `CheckboxList.qml`, `StatGrid.qml`) vs. screen-specific bodies (one `.qml` per `QmlOverlay` consumer, `Capital.qml`, ...). Shared widgets live in `src/presentation/ui/qml/<Widget>/` (§1); a `.qml` used by exactly one screen's one dialog stays there too — do not create a screen-local `.qml` folder elsewhere.
- **5.4 Naming.** Every interactive element MUST declare a stable `objectName` — the only thing `qml_item()`/`find_qml_item()` can search on; never use a generated index as the only test identity. Properties `camelCase` (`isConfigDirty`); signals `camelCase` verb phrases (`runRequested`, `chosen`, `toggled`).

## 6. 🎨 Design Practices & Visual Excellence

- **6.1 Design system & theme consistency.** See §3 — a hard gate, not a style preference.
- **6.2 Responsive sizing, no rigid fixed geometry.** Never hardcode rigid pixel `width`/`height` on modals, dialogs, popups, or cards. Use Qt Quick Layouts / `Column`/`Row` with `Layout.fillWidth`/`fillHeight` where applicable. Interior scrollable containers declare `ScrollView { clip: true }`.
- **6.3 Synchronized table column proportions.** For any data table/header grid built in QML, column widths MUST be declared centrally and both header and row delegates bind to the same definition. A `fillWidth` `Text` in either — header or row — needs **both** `elide: Text.ElideRight` and `Layout.minimumWidth: 0` together: `RowLayout` never shrinks the item below its un-elided `implicitWidth` without the second property, and without the first the un-elided glyphs still paint past the (now-shrunk) box into the next column regardless of what the box's own `width` reports — checked by reading `contentWidth`, not `width`, since `width` alone can look correctly shrunk while the painted text still overflows it. Apply this to a shared component's header cells too (`DataTable.qml`'s `Repeater` delegate), not only to each caller's own row delegate — a shared header serves every table using it, so missing it there reproduces in all of them at once.
- **6.4 Micro-animations.** Subtle, non-blocking transitions (**150–250ms**) are welcome once a widget is functionally correct — never before. Do not add decorative animation to render-sensitive surfaces (never applies to the chart, which stays QtWidgets regardless — §0).
- **6.5 Security & UI injection defense.** Always declare `textFormat: Text.PlainText` on `Text` items rendering dynamic or external data (trade logs, error messages, symbol names, raw exception text).
- **6.6 High-performance model-view.** A repeated, dynamic collection that can exceed 20 items, update incrementally, or be virtualized MUST be backed by a Python `QAbstractListModel` (`TradeLogModel`, `IndicatorScriptListModel`, `LogModel`) — it emits `dataChanged` per row instead of the wholesale rebuild §4.2 measures for a `Repeater`-over-list-of-dicts model. A small static list or one-shot form (`SelectList`/`CheckboxList`/`StatGrid`'s own rows) may use a plain `QVariantList` property only when it is not transforming domain data at scale. Keep `Repeater` delegates lean; instantiate detail sections on-demand via `Loader` or collapsible panels.

## 7. 🧪 QML Quality Assurance & Testing

- **Sanity verification**: every `.qml` must construct cleanly — no syntax errors, unbound property warnings, null pointer errors. `QmlOverlay` (`src/presentation/ui/qml/host.py`) turns a failed load into a raised `RuntimeError` instead of silently rendering a blank box; every widget host must do the same, not render-and-hope.
- **Widget VM tests need no GUI** (§1.2) — the majority of a widget's coverage lives there, not in a rendered test.
- **Render tests are thin, on purpose**: only prove the `.qml` loaded and its bindings point at properties the VM actually has — the render-time class of error `mypy`/`ruff` cannot see. Do not duplicate VM-level logic assertions in a render test.
- **Reaching into a rendered scene**: use `qml_item(root, "objectName")` (`tests/conftest.py`) for `Repeater` delegates and ordinary visual descendants (§4.3). Qt `Popup` items are the one exception, detached from `childItems()` the other direction — use `overlay_root.findChild(object, "objectName")`. Never weaken either kind of test into a Presenter/private-property assertion merely because the item is inconvenient to find.
- **Never hold a delegate reference across a refresh** (§4.2) — re-look-up after every `rowsChanged`/`optionsChanged`/`cardsChanged`.
- **Simulate real input, not a guessed signal signature** (§4.4) — `QTest.keyClicks`/`QTest.mouseClick` over hand-invoking a signal.

## 8. 🔍 UI Preview Convention & Live Tooling (BOT-031)

- Every screen package in `src/presentation/ui/screens/<screen>/` and reusable component (`src/presentation/ui/components/sidebar/`) MUST have a `preview.py` exposing `build_preview() -> QWidget`.
- Run: `.\scripts\preview-qml.ps1 <screen_name>` / `--list` — it previews QtWidgets screens too, despite the name.
- Guard test: `tests/unit/presentation/ui/test_preview_fixtures_exist.py`.

## 9. Open items

There is no dedicated tracking place for these two yet; keep them here until they land in a real
task/epic:

- `QmlOverlay.root_object`'s docstring ("for tests to `findChild` into") is only true for static
  items, not for `Repeater` delegates (§4.3) — a small doc fix.
- `SymbolPicker.qml` hand-rolls the backdrop/modal card/keyboard handling on an `Item` instead of
  using `Popup`/`Dialog` (§0.1) — not fixed yet because there is no production host to verify
  against; it will be rebuilt to this rule later.
