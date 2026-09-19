# EPIC-025F — Phase 5: build on the Engine's `EPIC-001D` (`NavigationService`, regions, screen lifecycle)

- **Status:** 🔴 Backlog — **blocked by ❓ O2** (ADR §3) and by the Engine-side task
- **Repositories:** Elite (the consumer) · Engine (the mechanism — `TASK-043`, referencing `EPIC-001D`)
- **Blocked by:** E
- **Read first:** HLD §5 (the Engine / application split); the Engine's
  `Tasks/epics/EPIC-001_ui_engine_foundation/incomplete/EPIC-001D_runtime_slot_registry.md`;
  the Engine's `examples/student_management/docs/ui_extension_lifecycle.md` (the ordering:
  `QApplication` before `boot()`).

## 1. What to do (application side)

1. Replace `ScreenRegistry` (`EPIC-016`) with the Engine's `NavigationService`: routes come from
   `screen` contributions; `RESTORE` is distinguished from `USER_INTENT` (`BUG-104` / `BUG-107`); a
   `can_leave()` guard protects an action in flight (`async-ui-action-rule` §1).

   **Inherits Phase 4's own unfinished half of `EPIC-025E` §1 step 6** (`EPIC-025E`'s own §1 step 6
   addendum, 2026-09-19): all four `LEGACY_SCREEN_MODULES` entries (`DashboardScreenModule`/
   `TradingScreenModule`/`DatabaseScreenModule`/`BacktestScreenModule`, `shell/legacy_screens.py`)
   still register through `AbstractScreenModule`, not a `ScreenContribution` — Phase 4 could move
   each screen's *files* (PRs 4.4b/4.4c/4.4d) but could not retire the mechanism itself, because
   that mechanism is this step. Converting all four at once, the shape `legacy_screens.py`'s own
   docstring already commits to, is part of this step's own scope, not a separate follow-up.
2. The application's `IContributionRegistry` is rebuilt on the Engine's slot registry (the
   application keeps the **kinds** — that is policy).
3. Every new Engine API is declared in `engine_capabilities.py` (`BOT-133`).
4. The Engine's screen conformance suite runs against **every** surface of this application.

## 2. Done when

- `main_window.py` imports no screen; navigation is built entirely from self-description.
