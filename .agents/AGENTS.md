# Development Guidelines

- **Installation & Dependencies (Sagittarius Engine Setup)**:
  - Option 1 (GitHub Repository): `pip install git+https://github.com/anhembedded/Sagittarius-Engine.git`
  - Option 2 (Local Editable): `pip install -e Sagittarius-Engine`
  - Apply SOLID wherever practical to improve clarity and testability.
  - **S**ingle Responsibility Principle (SRP): One reason to change. Split logic into single-purpose modules/files.
  - **O**pen/Closed Principle (OCP): Prefer extending behavior via new classes/interfaces over modifying tested code.
  - **L**iskov Substitution Principle (LSP): Subclasses must be fully substitutable for their base types.
  - **I**nterface Segregation Principle (ISP): Keep interfaces role-specific and lean.
  - **D**ependency Inversion Principle (DIP): High-level modules depend on abstractions, not concrete implementations.

- **Clean Architecture & 4-Layer Boundaries**:
  - Maintain clean boundaries across layers: **Domain** (Pure) $\rightarrow$ **Application** (Use Cases/Ports) $\rightarrow$ **Interface Adapters** (CLI/UI Presenters) $\rightarrow$ **Infrastructure** (DB/API/Frameworks).
  - Never leak Infrastructure concerns (SQLAlchemy, `sagittarius_engine`, exchange SDKs) into Domain or Application layers.
  - Prioritize building reusable abstraction base layers (base cards, base dialogs, base presenters/view models) over concrete duplication.

- **Strong Typing & Immutability**:
  - Always use explicit type annotations (avoid `Any`). Use `dataclasses` (with `frozen=True` where possible) or `Pydantic` models over raw dictionaries.
  - Strive for pure functions; never mutate arguments in-place; avoid mutable default arguments (`func(items=[])`).
  - No multiple inheritance: use composition over inheritance.

- **No Hardcoding, No Magic Numbers & Centralized Configuration**:
  - Avoid hardcoding parameters, default values, magic numbers, magic strings, or styling tokens directly into components or logic.
  - Every numeric value must be declared as a named constant or configuration key (`config_keys.py`, `user_config.json`, `constants.py`).
  - Strategy and indicator parameters must be declared dynamically via parameter schemas (`input_int`, `input_float`, etc.).

- **QML & Declarative UI Standards (See `.agents/rules/qml-rule.md`)**:
  - Keep QML strictly declarative; all business logic, validation, state machines, and calculations reside in Python (`Presenter`, `ViewModel`, `Domain`).
  - Use reactive property bindings; never break bindings with imperative assignments inside signal handlers.
  - Break down large monolithic QML files (> 300 lines) into modular, reusable components (`ModalDialogCard.qml`, `BotParamField.qml`, `DynamicTabBar.qml`).
  - Prefer declarative `states: [...]` and `transitions: [...]` over complex nested ternary expressions for elements with 3+ states.
  - Apply non-intrusive micro-animations (150ms – 250ms) for visual polish via `Behavior on color / opacity / height`.
  - Always enforce `textFormat: Text.PlainText` on `Text` items rendering dynamic or external data to prevent UI injection.

- **Dynamic Responsive UI Sizing & Synchronized Table Columns**:
  - Never hardcode rigid fixed `width`/`height` on modals or cards. Use `preferredWidth` and `preferredHeight` clamped to available overlay boundaries.
  - Ensure all interior scrollable containers use `ScrollView { clip: true }` and responsive content sizing.
  - For all tables and grids with headers, column widths MUST be declared centrally as a single source of truth (proportional to container width with safe minimum floors) and bound directly to both header and row delegates to guarantee 100% synchronized alignment during window resize and splitter movements.

- **Domain-Driven Precision Terminology**:
  - Maintain exact domain terms: Strategy-specific parameters must be labeled **"Thông số Chiến lược"** (`Strategy Parameters`), distinct from general Bot system settings.

- **No Function-Local / Lazy Imports (Tuyệt đối không dùng Local Import)**:
  - All module, class, function, and type imports MUST be declared at the top of the file (top-level imports) adhering strictly to PEP 8.
  - Never place `import ...` or `from ... import ...` inside functions, methods, slots, test cases, or nested scopes. The ONLY permitted indented import is inside `if TYPE_CHECKING:` guards at the top level for static typing annotations.

- **Single-Scope Cohesion & Colocation (Gom chung thành phần liên quan vào cùng 1 Scope / Single Source of Truth)**:
  - Tightly coupled elements defining the same domain lifecycle, state machine, or configuration MUST be co-located within the same single file or module scope (e.g., State Enum + Event Enum + Transition Matrix + UI mode mappings in a single `*_fsm_matrix.py`).
  - Do NOT fragment tightly coupled definitions across multiple scattered files where understanding a single feature lifecycle requires jumping across 4-5 distant modules.

- **Async Action Ownership, Data Truth & Benchmarking**:
  - Every UI-affecting background action needs an `action_id`/generation and immutable input snapshot; only the still-active action may mutate the ViewModel/FSM/chart or trigger a follow-up action. Ignore and log stale callbacks.
  - Cancellation is cooperative and idempotent. It must reach every compute pass, never publish a late success/failure, and restore the correct pre-action state.
  - Range coverage needs UTC + timeframe-cadence gap checks; exchange filters come from symbol metadata, not hard-coded capital thresholds.
  - History snapshots are immutable, provenance-rich and memory-bounded. Performance/ETA claims require a reproducible benchmark, not an unconditional millisecond SLA.


- **UI Icon Assets & Theme-Tinted Rendering**:
  - All visual iconography in the UI MUST be defined as clean, standardized SVG vector files in `src/presentation/ui/assets/icons/` (following Lucide/Feather icon standards).
  - Never use raw Unicode emoji or character glyphs for UI icons when SVG assets are appropriate.
  - Always render icons via the centralized theme image provider `image://icons/<name>/<token>`.

- **UI Preview Convention & Live Tooling (BOT-031)**:
  - Every screen package (`src/presentation/ui/screens/<name>/`) and reusable component (`src/presentation/ui/components/sidebar/`) MUST contain a `preview.py` declaring `build_preview() -> QWidget` for fast, standalone rendering without full engine boot.
  - Run previews live via `.\scripts\preview-qml.ps1 <screen>` or inspect available targets with `.\scripts\preview-qml.ps1 --list`.


- **Testing & Local CI/CD**:
  - Every new feature/screen ships with sanity tests in `tests/sanity/` (DI sanity + UI sanity) alongside unit tests.
  - Bug fixes must always include a reproducing regression test first.
  - Validate changes locally using `.\scripts\ci-local.ps1 -UnitOnly`.
  - Async lifecycle changes also require deterministic stale-callback and cancellation race tests; do not use sleep-based timing tests as proof.

- **Proactive Inconsistency Challenge & Constructive Pushback**:
  - The AI assistant MUST actively challenge/refute user requests if they introduce inconsistencies, anti-patterns, layer violations, or break established domain principles.
  - Never blindly follow contradictory instructions; explain the issue and propose a clean, consistent alternative.

- **Git Commits & Version Control**:
  - **DO NOT** commit code changes autonomously. Always wait for explicit user permission.
  - When committing upon request, follow `.agents/rules/commit-rule.md` and include the mandatory trailer:
    `Co-Authored-By: Antigravity <noreply@google.com>`
