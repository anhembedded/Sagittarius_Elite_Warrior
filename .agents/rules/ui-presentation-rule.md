---
name: UI Presentation Layer Rule
description: Quy tắc tầng presentation — bố cục MVP trio, responsive sizing, icon theme-tinted, thuật ngữ domain, và quy ước preview.py bắt buộc cho mọi UI package.
trigger: on_file_change
patterns:
  - "**/*.qml"
  - src/presentation/**/*.py
---

# UI & PRESENTATION LAYER RULES

> **Nguồn (2026-08-25):** nội dung dưới đây được **chuyển nguyên văn** từ
> `code-rule.md` khi file đó được tách theo abstraction level. Không có quy tắc
> nào bị đổi nghĩa, thêm hay bớt trong lần tách này — chỉ đổi chỗ ở.

**Phân vai với [`qml-rule.md`](qml-rule.md):** file đó là nguồn chuẩn đầy đủ cho
mọi thứ *bên trong* file `.qml` (declarative binding, states/transitions,
model-view, injection defense, tiêu chuẩn thiết kế). File này giữ phần
**tầng presentation nói chung** — bố cục thư mục Python, quy ước preview,
thuật ngữ, tài sản icon — cộng một mục lục ngắn các tiêu chuẩn QML để không
ai bỏ sót chúng. Mục 1 dưới đây là **chỉ mục**, không phải bản sao: chi tiết
và ví dụ code nằm ở `qml-rule.md`.

Coordinator Pattern đã chuyển sang
[`async-ui-action-rule.md`](async-ui-action-rule.md) vì nó là quy tắc về sở hữu
tác vụ nền, không phải về trình bày.

---

- **QML Standards & Declarative Guidelines (Strict Adherence to `qml-rule.md`):**
  - **Separation of Logic & UI**: QML files are purely declarative views. Business logic, calculations, domain validations, and state machines reside strictly in Python (`Presenter`, `ViewModel`, `Domain`). UI triggers ViewModel actions via slots/methods.
  - **Reactive Property Bindings**: Bind QML element properties directly to `viewModel` properties and `Theme` singletons. Never break bindings with imperative assignments inside signal handlers.
  - **Component Modularization & SRP**: Break down large monolithic QML files (> 300 lines) into focused, reusable components (`ModalDialogCard.qml`, `BotParamField.qml`, `DynamicTabBar.qml`).
  - **Declarative `States` and `Transitions`**: For elements with 3+ visual states (e.g., `IDLE`, `HOVER`, `PRESSED`, `DIRTY`, `DISABLED`), prefer declarative `states: [...]` and `transitions: [...]` over complex nested ternary expressions.
  - **Micro-Animations for Feedback**: Use subtle non-intrusive micro-animations (150ms – 250ms) via `Behavior on color / opacity / height` for smooth transitions without blocking the UI thread.
  - **Security & UI Injection Defense**: Always enforce `textFormat: Text.PlainText` on `Text` items rendering dynamic or external data (trade logs, error messages, symbol names) to prevent HTML/RichText UI injection.
- **Dynamic Responsive UI Sizing & Synchronized Table Columns:**
  - Never hardcode rigid fixed pixel dimensions (`width`/`height`) on modals, dialogs, popups, or cards. Use `preferredWidth` and `preferredHeight` dynamically clamped to available overlay boundaries.
  - All scrollable inner containers must declare `ScrollView { clip: true }` and responsive content widths.
  - For all tables and grids with headers, column widths MUST be declared centrally as a **Single Source of Truth** and bound directly to both header and row delegates to guarantee 100% synchronized alignment during window resize and splitter movements.
- **UI Icon Assets & Theme-Tinted Rendering:**
  - All visual iconography in the UI MUST be defined as clean, standardized SVG vector files in `src/presentation/ui/assets/icons/` (following Lucide/Feather icon standards). Never use raw Unicode emoji for UI icons.
  - Always render icons via the centralized theme image provider `image://icons/<name>/<token>`.
- **Domain-Driven Precision Terminology:**
  - Strategy parameters must be labeled **"Thông số Chiến lược"** (`Strategy Parameters`), distinct from general Bot system settings.
- **MVP Trio Screen Directory Layout:**
  - For a screen under `src/presentation/ui/screens/<name>/`, keep `<name>_presenter.py`, `<name>_view.py`, `<name>_view_model.py`, and QML files flat at the top level of the screen's folder. Group only helper modules into `<name>/logic/` or `<name>/helpers/` when size warrants it.
- **UI Preview Convention & Live Tooling (BOT-031):**
  - Every UI package (`src/presentation/ui/screens/<name>/` and `src/presentation/ui/components/sidebar/`) MUST maintain a `preview.py` declaring `build_preview() -> QWidget` for fast, standalone local rendering without full engine boot.
  - Run preview live via `.\scripts\preview-qml.ps1 <screen>` or inspect available targets with `.\scripts\preview-qml.ps1 --list`. Enforced via guard test `tests/unit/presentation/ui/test_preview_fixtures_exist.py`.
