# 🎨 QML & UI DEVELOPMENT STANDARDS

All UI components and QML files developed for the **Sagittarius Elite Warrior** project MUST strictly adhere to these declarative guidelines, architecture patterns, and design standards.

---

## 1. 🧩 Code Practices & Architecture Separation

### 1.1 Strict Separation of UI and Business Logic
- **QML is Purely Declarative View**: QML files must only define visual layout, theme bindings, micro-animations, and user interaction signals.
- **No Complex Inline JavaScript**: Move all calculations, data transformations, domain validation, and state machines into Python (`Presenter`, `ViewModel`, `Domain`, `Use Cases`). Small view-local helpers (for example focus handling, invoking a ViewModel command, or resetting an already-rendered input) are permitted only when they do not duplicate a business rule, transform a domain schema, or become a second source of state.
- **One-Way Command Dispatch**: UI triggers actions by invoking ViewModel slots/methods (e.g., `viewModel.requestRun()`, `viewModel.saveSettings()`). The Presenter handles the business logic and updates ViewModel properties.

### 1.2 Reactive Property Bindings (Over Manual Assignment)
- **Automatic Reactivity**: Always bind QML element properties directly to `viewModel` properties or theme singletons (e.g., `text: viewModel.resultText`, `enabled: viewModel.controlsEnabled`, `visible: viewModel.isConfigDirty`).
- **Never Break Bindings with Imperative Assignments**: Avoid assigning properties imperatively inside signal handlers (e.g., avoid `onClicked: myLabel.text = "Done"`). Update the underlying `viewModel` property from Python instead.

### 1.3 Component Modularization & Single Responsibility (SRP)
- **Break Down God Components**: Treat 300 lines as a mandatory review threshold, not a blind line-count failure. Break a component when it mixes separate responsibilities, repeats a pattern, or makes its user journey hard to test; do not split cohesive layout markup merely to satisfy a number.
  - Base cards & dialogs: `ModalDialogCard.qml`, `MetricCard.qml`
  - Reusable inputs: `BotParamField.qml`, `DynamicTabBar.qml`
  - Screen sub-panels: `BackTestToolbar.qml`, `TradeLogsTable.qml`, `TradeLogsDetailSection.qml`
- **Component File Structure**: Reusable components reside in `src/presentation/ui/components/`; screen-specific subcomponents reside directly in their screen folder `src/presentation/ui/screens/<screen_name>/`.

### 1.4 Consistent Naming Conventions
- **Descriptive Visual IDs**: Use clear, camelCase IDs reflecting purpose (e.g., `id: backtestStaleWarningBanner`, `id: btnRunBacktest`, `id: tradeLogsTable`).
- **Unique Testable IDs**: Every interactive element (Button, TextField, ComboBox, Modal) MUST declare a descriptive QML `id` **and** a stable `objectName`. `id` supports readable bindings; `objectName` is the public automation contract for `qml_item()` and desktop E2E. Never use a generated index as the only test identity.
- **Property & Signal Naming**:
  - Properties: `camelCase` (e.g., `isConfigDirty`, `selectedTimeframe`, `controlsEnabled`).
  - Signals: `camelCase` verb phrases (e.g., `runRequested`, `syncClicked`, `modalDismissed`).

---

## 2. 🎨 Design Practices & Visual Excellence

### 2.1 Design System & Theme Consistency
- **Centralized Tokens**: New feature code must use the centralized Theme tokens rather than introducing literal colours, fonts, spacing, or radii. The existing UI exposes a flat API such as `Theme.bg`, `Theme.bgCard`, `Theme.border`, `Theme.textPrimary`, `Theme.accent`, `Theme.success`, `Theme.danger`, and `Theme.muted` -- it does **not** expose `Theme.colors`, `Theme.fonts`, `Theme.spacing`, or `Theme.radii`. Literal fallback values are allowed only inside shared compatibility primitives while the legacy UI is migrated; feature QML must not add new fallbacks or duplicate palette literals.
- **Always Use ThemeSingleton**: Use the project API above. If a required semantic token (for example `warning`, `buttonHover`, spacing, or radius) does not exist, add it once to the palette/theme bridge or reuse a shared primitive; do not make up a parallel `Theme.colors.*` API in one QML file.
- **Theme-Tinted Vector Icons**: Use SVG icons loaded via `image://icons/<name>/<token>`. Never use raw emoji or raster bitmaps for UI icons.

### 2.2 Dynamic Responsive UI Sizing (No Rigid Fixed Geometry)
- **Zero Fixed Dimensions on Containers**: Never hardcode rigid pixel `width` or `height` on modals, dialogs, popups, or cards.
- **Clamped Dynamic Sizing**: Use `preferredWidth` and `preferredHeight` dynamically clamped to available overlay or viewport boundaries (e.g., `Math.min(parent.width * 0.9, 720)`).
- **Layout Managers**: Use Qt Quick Layouts (`ColumnLayout`, `RowLayout`, `GridLayout`) with `Layout.fillWidth: true` and `Layout.fillHeight: true`.
- **Clipped Scrolling**: Ensure all interior scrollable containers declare `ScrollView { clip: true }` with responsive content sizing.

### 2.3 Synchronized Table Column Proportions
- **Single Source of Truth for Columns**: For all data tables and header grids, column widths MUST be declared centrally in a single configuration/mapping.
- **Synchronized Delegates**: Header delegate and row cell delegates MUST bind directly to the same column width definition to guarantee 100% alignment during window resize and splitter movements.

### 2.4 Micro-Animations for Feedback & Polish
- **Subtle Transitions**: Where feedback benefits comprehension, use non-intrusive micro-animations (normally 150ms – 250ms) with `Easing.InOutQuad` or `Easing.OutCubic`:
  - Hover & Pressed state color fades: `Behavior on color { ColorAnimation { duration: 150 } }`
  - Border highlight transitions: `Behavior on border.color { ColorAnimation { duration: 150 } }`
  - Modal backdrop and panel fade/scale: `NumberAnimation on opacity`, `NumberAnimation on scale`
  - Warning banner drop-down: `NumberAnimation on height` or `NumberAnimation on y`
- **Never Block User Flow**: Animations must be asynchronous and unobtrusive; never prevent user clicks or lock the UI thread. Do not add decorative animation to high-frequency or render-sensitive surfaces (charts, pan/zoom, large tables) until a benchmark proves it is within the interaction budget.
- **Native Chart Interaction**: The Backtest native chart wrapper may own only
  gesture-to-viewport conversion, axis/tooltip/FPS presentation and bindings to
  `NativeChartItem`. It must not pack snapshots, calculate indicators, infer
  business state or duplicate Presenter/adapter data decisions. Keep text,
  axes and tooltip updates separate from retained bulk geometry; pan/wheel/
  pointer input must not rebuild OHLCV, volume, indicator or marker buffers.
  Give every tested handler/overlay a stable `objectName`; use Theme tokens and
  no decorative animation until the standard profile benchmark proves it fits
  the interaction budget.

---

## 3. ⚖️ Code + Design Integration & Security

### 3.1 Declarative `States` and `Transitions`
- **Multi-State Elements**: When an element possesses 3 or more distinct visual states (e.g., `IDLE`, `HOVER`, `PRESSED`, `DIRTY`, `DISABLED`), prefer declarative `states` and `transitions` over nested ternary expressions. Two simple, directly-related visual branches may remain a binding.
  ```qml
  states: [
      State {
          name: "dirty"
          when: viewModel.isConfigDirty
          PropertyChanges { target: btnRun; color: Theme.colors.amber; text: "CẬP NHẬT LẠI" }
      },
      State {
          name: "running"
          when: !viewModel.controlsEnabled
          PropertyChanges { target: btnRun; opacity: 0.5; enabled: false }
      }
  ]
  transitions: [
      Transition {
          ColorAnimation { properties: "color,border.color"; duration: 180 }
          NumberAnimation { properties: "opacity"; duration: 180 }
      }
  ]
  ```

### 3.2 High-Performance Model-View Patterns
- **C++ / Python Model Backing**: A repeated, dynamic collection that can exceed 20 items, update incrementally, or be virtualized MUST be backed by a Python `QAbstractListModel` (for example `TradeLogModel`, `IndicatorScriptListModel`, `LogModel`). A small static list or a one-shot form may use a QML model only when QML is not transforming domain data.
- **ListView Delegate Optimization**: Keep delegates lean and instantiate detail sections on-demand (via `Loader` or collapsible panels).

### 3.3 Security & UI Injection Defense
- **Enforce PlainText**: Always declare `textFormat: Text.PlainText` on `Text` items rendering dynamic or external data (trade logs, error messages, symbol names, parameter labels, raw exception text) to prevent HTML/RichText injection.

---

## 4. 🧪 QML Quality Assurance & Testing

- **Sanity Verification**: Every QML file must construct cleanly without QML syntax errors, unbound property warnings, or null pointer errors during `tests/sanity/`.
- **Verify Clean Load**:
  ```python
  assert quick_widget.errors() == []
  ```
- **Test Visual Hierarchy**: Use `qml_item(root, "objectName")` for repeated delegates and ordinary visual descendants rather than querying non-visual QObject trees. Qt `Popup` items are detached from `QQuickItem.childItems()`; for that framework boundary, use `overlay_root.findChild(object, "objectName")` against the real overlay root. Do not weaken either kind of test into a Presenter/private-property assertion merely because the item is inconvenient to find.

---

## 5. 🔍 UI Preview Convention & Live Tooling (BOT-031)

To preview screens and UI components fast during local UI development without booting the entire Sagittarius Engine or DI container:
- **Mandatory `preview.py` per UI Package**: Every screen package in `src/presentation/ui/screens/<screen>/` and reusable component (`src/presentation/ui/components/sidebar/`) MUST have a `preview.py` file exposing:
  ```python
  def build_preview() -> QWidget:
      """Constructs view + mock ViewModel + sample data ready for .show()."""
  ```
- **Preview CLI Runner**: Use `scripts/preview-qml.ps1` to test screens live:
  ```powershell
  .\scripts\preview-qml.ps1 --list
  .\scripts\preview-qml.ps1 <screen_name>  # e.g., backtest, dashboard, data_management, settings, sidebar
  ```
- **Automated Guard Tests**: Enforced automatically via AST and offscreen load verification in `tests/unit/presentation/ui/test_preview_fixtures_exist.py`.
