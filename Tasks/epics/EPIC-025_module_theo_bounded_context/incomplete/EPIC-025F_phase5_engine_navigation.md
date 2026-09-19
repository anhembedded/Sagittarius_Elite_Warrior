# EPIC-025F — Phase 5: build on the Engine's `EPIC-001D` (`NavigationService`, regions, screen lifecycle)

- **Status:** 🔴 Backlog — **blocked by ❓ O2** (ADR §3) and by the Engine-side task
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
3. Every new Engine API is declared in `engine_capabilities.py` (`BOT-133`).
4. The Engine's screen conformance suite runs against **every** surface of this application.

## 2. Done when

- `main_window.py` imports no screen; navigation is built entirely from self-description.
