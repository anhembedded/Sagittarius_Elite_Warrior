---
name: UI Presentation Layer Rule
description: Quy tắc tầng presentation — bố cục MVP trio, responsive sizing, icon theme-tinted, thuật ngữ domain, và quy ước preview.py bắt buộc cho mọi UI package.
trigger: on_file_change
patterns:
  - "**/*.qml"
  - src/presentation/**/*.py
---

# UI & PRESENTATION LAYER RULES

**Phân vai với [`qml-rule.md`](qml-rule.md):** file đó là nguồn chuẩn đầy đủ cho
mọi thứ *bên trong* file `.qml`. File này giữ **tầng presentation nói chung** —
bố cục thư mục Python, quy ước preview, thuật ngữ, tài sản icon — cộng một mục
lục ngắn các tiêu chuẩn QML. Mục đầu dưới đây là **chỉ mục**, không phải bản
sao. Coordinator Pattern nằm ở
[`async-ui-action-rule.md`](async-ui-action-rule.md).

---

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
  - Never hardcode rigid fixed pixel dimensions (`width`/`height`) on modals, dialogs, popups, or cards. Use `preferredWidth`/`preferredHeight` dynamically clamped to available overlay boundaries.
  - All scrollable inner containers must declare `ScrollView { clip: true }` and responsive content widths.
  - For tables and grids with headers, column widths MUST be declared centrally as a **Single Source of Truth** and bound to both header and row delegates, guaranteeing synchronized alignment during window resize and splitter movements.
- **UI Icon Assets & Theme-Tinted Rendering:**
  - All iconography MUST be standardized SVG vector files in `src/presentation/ui/assets/icons/` (Lucide/Feather standards). Never use raw Unicode emoji for UI icons.
  - Always render icons via the centralized theme image provider `image://icons/<name>/<token>`.
- **Domain-Driven Precision Terminology:** Strategy parameters must be labeled **"Thông số Chiến lược"** (`Strategy Parameters`), distinct from general Bot system settings.
- **MVP Trio Screen Directory Layout:** For a screen under `src/presentation/ui/screens/<name>/`, keep `<name>_presenter.py`, `<name>_view.py`, `<name>_view_model.py`, and QML files flat at the top level. Group only helper modules into `<name>/logic/` or `<name>/helpers/` when size warrants it.
- **UI Preview Convention & Live Tooling (BOT-031):**
  - Every UI package (`src/presentation/ui/screens/<name>/` and `src/presentation/ui/components/sidebar/`) MUST maintain a `preview.py` declaring `build_preview() -> QWidget` for standalone rendering without full engine boot.
  - Run via `.\scripts\preview-qml.ps1 <screen>` or `--list`. Enforced by guard test `tests/unit/presentation/ui/test_preview_fixtures_exist.py`.
