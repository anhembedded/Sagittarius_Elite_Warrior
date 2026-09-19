# EPIC-025F — Phase 5: build on the Engine's `EPIC-001D` (`NavigationService`, regions, screen lifecycle)

- **Status:** 🟡 In progress — unblocked 2026-09-19 (see the sequencing decision below); PR 5.1 (the
  in-app `NavigationService` prototype) landed the same day, merged as PR #241 (`370573b7`) after
  full gate green + independent review PASS. Remaining: retire `ScreenRegistry` and the 4
  `LEGACY_SCREEN_MODULES` entries, rebuild `IContributionRegistry` on the Engine's slot registry,
  migrate onto the Engine's `RegionHost`, declare new Engine APIs, run the conformance suite.
- **Repositories:** Elite (the consumer) · Engine (the mechanism — `TASK-043`, referencing `EPIC-001D`)
- **Blocked by:** E
- **Read first:** HLD §5 (the Engine / application split); the Engine's
  `Tasks/epics/EPIC-001_ui_engine_foundation/incomplete/EPIC-001D_runtime_slot_registry.md`;
  the Engine's `examples/student_management/docs/ui_extension_lifecycle.md` (the ordering:
  `QApplication` before `boot()`).

**Decided 2026-09-19 (Engine `TASK-043`'s own file, same decision recorded here since it
determines this phase's own unblock path).** The Engine's E3 (`NavigationService`) is triggered by
this phase landing a working `NavigationService`-shaped mechanism in this app's own tree first,
against `ScreenRegistry`'s current shape — the same harvest-first pattern Phase 1's contribution
mechanism already went through (Engine `TASK-043` E1, 2026-09-19) — not by the Engine building
`NavigationService` ahead of any live consumer. So this phase's own next executable step, once
picked up, is that in-app prototype (mirroring how the Engine's own
`examples/student_management/docs/ui_extension_lifecycle.md` resolved a parallel ordering
question), not waiting on the Engine to move first. Still blocked today only in the sense that no
session has started that prototype yet — not blocked on someone else's decision any more.

## 1. What to do (application side)

1. Replace `ScreenRegistry` (`EPIC-016`) with the Engine's `NavigationService`: routes come from
   `screen` contributions; `RESTORE` is distinguished from `USER_INTENT` (`BUG-104` / `BUG-107`); a
   `can_leave()` guard protects an action in flight (`async-ui-action-rule` §1).

   **PR 5.1 — the in-app `NavigationService` prototype, landed 2026-09-19.** The first slice of
   this step, following the epic's own harvest-first pattern (Phase 1's contribution mechanism,
   Phase 4's trading ports): the mechanism this app's `TASK-043` E3 decision calls for, built
   against `ScreenRegistry`'s current shape rather than waiting on the Engine to propose it first.
   `NavigationSource(str, Enum)` (`USER_INTENT`/`RESTORE`) in `src/core/contracts/`, mirroring
   `NavLocation`'s own placement/pattern; `INavigationService`/`NavigationService`
   (`src/support/ui_kit/registry/`) wrapping the existing `PresenterManager` router, with an
   optional constructor-injected `can_leave: Callable[[], bool] | None = None` — permissive by
   default (`architecture-rule.md` §7.2.1, "seam now, variant later": no screen today needs to
   block navigation, so the seam exists without a variant). `MainWindow.switch_screen()` (a real
   user click, always `USER_INTENT`) and boot's one initial navigation (now tagged `RESTORE`) both
   route through a shared private `_navigate()` helper calling `NavigationService.navigate()`,
   preserving `switch_screen()`'s exact external behaviour — all 5 existing
   `test_main_window_state.py` tests pass unchanged, since `can_leave` is permissive today.
   6 new unit tests in `tests/unit/support/ui_kit/registry/test_navigation_service.py`, including a
   mutation-style check (`pr-review` E12) that the `can_leave` guard is genuinely consulted, not
   decorative. **Deliberately does not yet**: retire `ScreenRegistry`, touch the 4
   `LEGACY_SCREEN_MODULES` entries, or make any screen (e.g. `TradingPresenter`) actually consume
   `source` to change behaviour (`BUG-104`'s class of bug stays fixed the current blunt way — route
   memory deleted entirely — until a screen has a real reason to read `source`). Those remain this
   step's own later slices, per this section's own scope.

   **Inherits Phase 4's own unfinished half of `EPIC-025E` §1 step 6** (`EPIC-025E`'s own §1 step 6
   addendum, 2026-09-19): all four `LEGACY_SCREEN_MODULES` entries (`DashboardScreenModule`/
   `TradingScreenModule`/`DatabaseScreenModule`/`BacktestScreenModule`, `shell/legacy_screens.py`)
   still register through `AbstractScreenModule`, not a `ScreenContribution` — Phase 4 could move
   each screen's *files* (PRs 4.4b/4.4c/4.4d) but could not retire the mechanism itself, because
   that mechanism is this step. Converting all four at once, the shape `legacy_screens.py`'s own
   docstring already commits to, is part of this step's own scope, not a separate follow-up.
2. The application's `IContributionRegistry` is rebuilt on the Engine's slot registry (the
   application keeps the **kinds** — that is policy).

   **The one blocking gap this needed is closed, 2026-09-19.** The Engine's `TASK-043` E1 harvest
   step needs this app's `place`/`surface_id` identities to already be opaque-string-typed before
   `ContributionDescriptor`/`ContributionRegistry`'s shape can move — verified by reading both
   sides: `surface_id: str` already was; `place: Place` was not, because `Place`
   (`core/contracts/place.py`) was a bare `Enum`, `isinstance(place, str)` was `False`. Fixed by
   the one-line, fully backward-compatible change this codebase already uses ~40 times elsewhere
   (`support/binance_gateway/contracts/trading_venue.py` and its siblings): `class Place(Enum)` →
   `class Place(str, Enum)`. Verified on this repo's own Python 3.12 that the mixin changes nothing
   observable — `str(Place.X)` still prints `"Place.X"` (this Python version's `(str, Enum)` does
   not adopt `StrEnum`'s different `__str__`), member-to-member equality/hash unaffected, and
   `grep` confirmed no existing call site compares a `Place` member against a bare string literal
   — only `isinstance(Place.X, str)` and `Place.X == "x"`, both newly `True`, changed at all. Full
   local ladder green: `ruff`/`mypy` clean (632 files), `tests/unit/architecture` 420, the 106
   tests across every file touching `Place`/`ContributionRegistry`/`ContributionDescriptor`, full
   `tests/unit`/`tests/sanity`/`tests/integration` all green. `Place` itself is unchanged as this
   app's own closed, HLD-governed vocabulary — only its runtime type gained the `str` mixin the
   Engine's own future mechanism needs to treat it as opaque. Documented on the Engine side too:
   `Sagittarius_Engine` `Tasks/in_progress/TASK-043_...md`'s E1 row.

   **The rendering half — this app's `IPlaceHost`/`WorkbenchSurface` — has now landed on the
   Engine side too, 2026-09-19 (`TASK-043` E2)**: `RegionKind` (the engine-owned, closed
   `QMainWindow` anatomy this app's own `Place`→dock/toolbar dispatch already encoded informally),
   `IRegionHost`, and `RegionHost`, harvested from this app's own `WorkbenchSurface`
   (`support/ui_kit/workbench_surface.py`) with `place` made opaque and the place→region mapping
   supplied by the caller at construction instead of hard-coded. **Not yet consumed here** — this
   app's own `WorkbenchSurface`/`IPlaceHost` are unchanged and still what every surface actually
   renders against; migrating onto the Engine's `RegionHost` is this step's own remaining work, not
   something today's harvest did on this app's behalf. Documented on the Engine side:
   `Sagittarius_Engine` `Tasks/in_progress/TASK-043_...md`'s E2 row.
3. Every new Engine API is declared in `engine_capabilities.py` (`BOT-133`).
4. The Engine's screen conformance suite runs against **every** surface of this application.

## 2. Done when

- `main_window.py` imports no screen; navigation is built entirely from self-description.
