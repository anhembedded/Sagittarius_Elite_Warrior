---
name: UI Presentation Layer Rule
description: Presentation-layer rules — MVP trio directory layout, responsive sizing, theme-tinted icons, domain terminology, and the preview.py convention required for every UI package.
trigger: on_file_change
patterns:
  - "**/*.qml"
  - src/presentation/**/*.py
---

# UI & PRESENTATION LAYER RULES

**Division of labour with [`qml-rule.md`](qml-rule.md):** that file is the complete, authoritative
source for everything *inside* a `.qml` file. This file covers **the presentation layer in
general** — Python directory layout, the preview convention, terminology, icon assets — plus an
**index** (not a copy) of the QML standards. The Coordinator Pattern lives in
[`async-ui-action-rule.md`](async-ui-action-rule.md).

- **QML Standards & Declarative Guidelines (Strict Adherence to `qml-rule.md`):**
  > QtWidgets is the app-wide default; QML is opt-in **per widget** (a modal body, a panel),
  > always embedded inside a QtWidgets chrome via `QQuickWidget`. The shell and the chart
  > (`components/chart_card/`) never become QML — `qml-rule.md` §0. The list below is a table of
  > contents only; §1–§9 there hold the real rules, including the "1 widget = 1 `.qml` + 1
  > private `_vm.py`" architecture and when to skip that ViewModel entirely (a widget that only
  > forwards a screen ViewModel's properties 1:1, with no derived value and no reuse across
  > screens, binds straight to that ViewModel instead of wrapping it).
  - **Separation of Logic & UI**: QML files are purely declarative views. Business logic, calculations, domain validations, and state machines reside strictly in the widget's own `_vm.py` or the screen's `Presenter`/`ViewModel`/`Domain`. UI triggers actions via slots/methods.
  - **Reactive Property Bindings**: Bind QML element properties directly to `vm` properties and `Theme` singletons. Never break bindings with imperative assignments inside signal handlers.
  - **Component Modularization & SRP**: Break down monolithic QML files (> 300 lines) into focused, reusable components. Shared shapes: `SelectList.qml`, `CheckboxList.qml`, `StatGrid.qml` (`src/presentation/ui/qml/`).
  - **Declarative `States` and `Transitions`**: For elements with 3+ visual states (e.g., `IDLE`, `HOVER`, `PRESSED`, `DIRTY`, `DISABLED`), prefer declarative `states: [...]` and `transitions: [...]` over complex nested ternary expressions.
  - **Micro-Animations for Feedback**: Use subtle non-intrusive micro-animations (150ms – 250ms) via `Behavior on color / opacity / height` for smooth transitions without blocking the UI thread.
  - **Security & UI Injection Defense**: Always enforce `textFormat: Text.PlainText` on `Text` items rendering dynamic or external data (trade logs, error messages, symbol names) to prevent HTML/RichText UI injection.
  - **Qt Quick gotchas (measured, not obvious)**: a `Repeater` accepts exactly one delegate — two sibling `Item`s under it silently collapse to the last one; it also destroys and recreates every delegate on any model change, so tests must never hold a delegate reference across a refresh. Full detail in `qml-rule.md` §4.
- **Dynamic Responsive UI Sizing & Synchronized Table Columns:**
  - Never hardcode rigid fixed pixel dimensions (`width`/`height`) on modals, dialogs, popups, or cards. Use `preferredWidth`/`preferredHeight` dynamically clamped to available overlay boundaries. Fixed size is only for a true leaf glyph (icon, small badge, divider) — never a container holding text or other widgets: it does not fix an overlap, it trades it for a same-severity "clipped at a different window size/DPI/locale" bug (Vietnamese UI strings run longer than English).
  - All scrollable inner containers must declare `ScrollView { clip: true }` and responsive content widths. At the screen level, `PageShell.set_workspace()` (`kit/page_shell.py`) already scroll-wraps both `main` and `rail` in a borderless `QScrollArea` — a screen whose content can outgrow its viewport (a panel with an optional sub-section, a tall form) gets this for free by passing its raw content widget; it does not need to hand-roll its own `QScrollArea` the way Backtest/Settings did before this existed.
  - For tables and grids with headers, column widths MUST be declared centrally as a **Single Source of Truth** and bound to both header and row delegates, guaranteeing synchronized alignment during window resize and splitter movements. A `fillWidth` `Text` in EITHER the header or the row delegate needs **both** `elide: Text.ElideRight` and `Layout.minimumWidth: 0` — `elide` alone does not let `RowLayout` shrink the item below its un-elided `implicitWidth`, and `Layout.minimumWidth: 0` alone does not stop the un-elided text from painting past its own (now-shrunk) box into the next column — a shared component (`DataTable.qml`) needs this on its header cells too, not only on each caller's own row delegate.
  - Two independent positioning systems must never float over the same corner/region of one surface — e.g. a `QWidget.move()`-positioned overlay (zoom buttons) and a chart library's own internal layout (pyqtgraph's `GraphicsLayout` label row, QML's own item positioning): neither one is aware of what space the other occupies, and nothing errors when they collide. Anchor the widget-level overlay to a corner/band the other system provably never renders into (measured, not assumed — see `chart_card/zoom_controls.py`'s own comment).
- **UI Icon Assets & Theme-Tinted Rendering:**
  - All iconography MUST be standardized SVG vector files in `src/presentation/ui/assets/icons/` (Lucide/Feather standards). Never use raw Unicode emoji for UI icons.
  - Always render icons via the centralized theme image provider `image://icons/<name>/<token>`.
- **Domain-Driven Precision Terminology:** Strategy parameters must be labeled **"Thông số Chiến lược"** (`Strategy Parameters`), distinct from general Bot system settings.
- **MVP Trio Screen Directory Layout:** For a screen under `src/presentation/ui/screens/<name>/`, keep `<name>_presenter.py`, `<name>_view.py`, `<name>_view_model.py`, and QML files flat at the top level. Group only helper modules into `<name>/logic/` or `<name>/helpers/` when size warrants it.
- **UI Preview Convention & Live Tooling (BOT-031):**
  - Every UI package (`src/presentation/ui/screens/<name>/` and `src/presentation/ui/components/sidebar/`) MUST maintain a `preview.py` declaring `build_preview() -> QWidget` for standalone rendering without full engine boot.
  - Run via `.\scripts\preview-qml.ps1 <screen>` or `--list`. Enforced by guard test `tests/unit/presentation/ui/test_preview_fixtures_exist.py`.
