# 🎨 QML & UI DEVELOPMENT STANDARDS

All UI components and QML files developed for the **Sagittarius Elite Warrior** project MUST strictly adhere to these declarative guidelines, architecture patterns, and design standards.

---

## 1. 🧩 Code Practices & Architecture Separation

### 1.1 Strict Separation of UI and Business Logic
- **QML is Purely Declarative View**: QML files must only define visual layout, theme bindings, micro-animations, and user interaction signals.
- **No Complex Inline JavaScript**: Move all calculations, data transformations, domain validation, and state machines into Python (`Presenter`, `ViewModel`, `Domain`, `Use Cases`).
- **One-Way Command Dispatch**: UI triggers actions by invoking ViewModel slots/methods (e.g., `viewModel.requestRun()`, `viewModel.saveSettings()`). The Presenter handles the business logic and updates ViewModel properties.

### 1.2 Reactive Property Bindings (Over Manual Assignment)
- **Automatic Reactivity**: Always bind QML element properties directly to `viewModel` properties or theme singletons (e.g., `text: viewModel.resultText`, `enabled: viewModel.controlsEnabled`, `visible: viewModel.isConfigDirty`).
- **Never Break Bindings with Imperative Assignments**: Avoid assigning properties imperatively inside signal handlers (e.g., avoid `onClicked: myLabel.text = "Done"`). Update the underlying `viewModel` property from Python instead.

### 1.3 Component Modularization & Single Responsibility (SRP)
- **Break Down God Components**: Avoid massive monolithic QML files (> 300 lines). Break complex screens into focused, reusable components:
  - Base cards & dialogs: `ModalDialogCard.qml`, `MetricCard.qml`
  - Reusable inputs: `BotParamField.qml`, `DynamicTabBar.qml`
  - Screen sub-panels: `BackTestToolbar.qml`, `TradeLogsTable.qml`, `TradeLogsDetailSection.qml`
- **Component File Structure**: Reusable components reside in `src/presentation/ui/components/`; screen-specific subcomponents reside directly in their screen folder `src/presentation/ui/screens/<screen_name>/`.

### 1.4 Consistent Naming Conventions
- **Descriptive Visual IDs**: Use clear, camelCase IDs reflecting purpose (e.g., `id: backtestStaleWarningBanner`, `id: btnRunBacktest`, `id: tradeLogsTable`).
- **Unique Testable IDs**: Every interactive element (Button, TextField, ComboBox, Modal) MUST declare a descriptive `id` or `objectName` for `qml_item()` lookup in automated tests.
- **Property & Signal Naming**:
  - Properties: `camelCase` (e.g., `isConfigDirty`, `selectedTimeframe`, `controlsEnabled`).
  - Signals: `camelCase` verb phrases (e.g., `runRequested`, `syncClicked`, `modalDismissed`).

---

## 2. 🎨 Design Practices & Visual Excellence

### 2.1 Design System & Theme Consistency
- **Centralized Tokens**: Strictly avoid hardcoded color hex codes, font sizes, margins, or corner radii.
- **Always Use ThemeSingleton**:
  - Colors: `Theme.colors.background`, `Theme.colors.cardBg`, `Theme.colors.accent`, `Theme.colors.textPrimary`, `Theme.colors.border`
  - Typography: `Theme.fonts.title`, `Theme.fonts.body`, `Theme.fonts.monospace`, `Theme.fonts.caption`
  - Spacing & Radii: `Theme.spacing.sm`, `Theme.spacing.md`, `Theme.spacing.lg`, `Theme.radii.card`, `Theme.radii.button`
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
- **Subtle Transitions**: Use non-intrusive micro-animations (150ms – 250ms) with `Easing.InOutQuad` or `Easing.OutCubic` to provide visual polish and tactile feedback:
  - Hover & Pressed state color fades: `Behavior on color { ColorAnimation { duration: 150 } }`
  - Border highlight transitions: `Behavior on border.color { ColorAnimation { duration: 150 } }`
  - Modal backdrop and panel fade/scale: `NumberAnimation on opacity`, `NumberAnimation on scale`
  - Warning banner drop-down: `NumberAnimation on height` or `NumberAnimation on y`
- **Never Block User Flow**: Animations must be asynchronous and unobtrusive; never prevent user clicks or lock the UI thread.

---

## 3. ⚖️ Code + Design Integration & Security

### 3.1 Declarative `States` and `Transitions`
- **Multi-State Elements**: When an element possesses 3 or more distinct visual states (e.g., `IDLE`, `HOVER`, `PRESSED`, `DIRTY`, `DISABLED`), prefer declarative `states` and `transitions` over nested ternary expressions:
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
- **C++ / Python Model Backing**: Use `QAbstractListModel` (`TradeLogModel`, `IndicatorScriptListModel`, `LogModel`) for lists exceeding 20 items to benefit from Qt's native virtualization and role-based updates.
- **ListView Delegate Optimization**: Keep delegates lean and instantiate detail sections on-demand (via `Loader` or collapsible panels).

### 3.3 Security & UI Injection Defense
- **Enforce PlainText**: Always declare `textFormat: Text.PlainText` on `Text` items rendering dynamic or external data (trade logs, error messages, symbol names, raw exception text) to prevent HTML/RichText injection.

---

## 4. 🧪 QML Quality Assurance & Testing

- **Sanity Verification**: Every QML file must construct cleanly without QML syntax errors, unbound property warnings, or null pointer errors during `tests/sanity/`.
- **Verify Clean Load**:
  ```python
  assert quick_widget.errors() == []
  ```
- **Test Visual Hierarchy**: Use `qml_item(root, "elementId")` to verify UI components rather than querying non-visual QObject trees.
