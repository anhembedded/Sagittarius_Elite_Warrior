# EPIC-025F — Phase 5: build on the Engine's `EPIC-001D` (`NavigationService`, regions, screen lifecycle)

- **Status:** ✅ **Application-side scope done (2026-09-19), by user decision.** PR 5.1 (the in-app
  `NavigationService` prototype) merged as PR #241 (`370573b7`). PR 5.2 (the 4 `LEGACY_SCREEN_MODULES`
  entries convert to `ScreenContribution`) merged as PR #242. PR 5.3 (`IContributionRegistry`'s panel
  half rebuilt on the Engine's own `ContributionRegistry`, after the user approved bumping Elite's
  installed Engine to its current `main`) merged as PR #243. PR 5.4 (`RegionHost` migration +
  capability declaration) merged as PR #244 (`b56b3da6`). PR 5.5 (`AbstractScreenModule` and dead
  `register_module()` seam retired, `INavigationService` DI integration) merged as PR #245.
  §2's "Done when" criterion re-verified directly (`main_window.py` imports zero screen modules).
  **Item 4 (PR 5.6, the Engine's screen conformance suite) is deliberately not folded into this
  closure — it is deferred, blocked on `Sagittarius_Engine`'s own `TASK-043` E3, which has not
  started on the Engine side** (verified by reading that repository's checkout directly, not
  assumed: E3 bundles "`NavigationService`, screen lifecycle + conformance suite", and its own row
  still reads "Consumer's Phase 5 has not started" — stale wording now that Elite's Phase 5 has
  fully landed, but the code confirms the substance: no conformance-suite mechanism exists anywhere
  in the Engine tree yet). Per `ONBOARDING.md` §9, this is not duplicated as a fake Elite-side task
  — `TASK-043` E3 already owns it; a future session picks this file back up once the Engine side
  lands, rather than leaving Phase 5 open indefinitely for work that belongs to a different repo.
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

   **PR 5.2 — all four `LEGACY_SCREEN_MODULES` entries convert, landed 2026-09-19.** Each becomes a
   `*_screen()` factory (`database_screen()`, `dashboard_screen()`, `trading_screen()`,
   `backtest_screen()`) owned by the module the screen actually belongs to, mirroring the exact
   shape `settings_screen()` established in `EPIC-025E` PR 4.4e — no longer carried by the shell
   through `shell/legacy_screen_adapter.py`, both it and `shell/legacy_screens.py` deleted in this
   pull request. `TradingModule`/`BacktestingModule` own two/one of the four respectively
   (`market_data` the other one) and call `registry.contribute_screen(...)` from their own
   `contribute()`.

   **A real bug found and fixed, not a file move.** `DashboardView`/`BackTestView`'s factories need
   `container` at *view* construction (`_contribution_table(container)`; `container.resolve(IConfig)`
   for the config-driven View choice) — `ScreenContribution.view_factory` takes zero arguments
   (`PresenterManager.navigate_to()` calls it that way, an Engine constraint), so `container` has to
   be closed over when the `ScreenContribution` itself is built. The first version stashed it in
   `register()`; the real gate caught that it is wrong — `register()`'s `context.container` is
   `RegisteringContainer`, a spy that refuses every `resolve()` call **permanently**, not only during
   registration (`shell/registering_container.py`'s own docstring), so a reference to it captured
   there and used later inside a screen's lazily-run view factory raised
   `ResolveDuringRegisterError` on a call with nothing to do with registration any more — caught by
   `tests/sanity/test_composition_root.py::test_every_navigable_route_constructs[dashboard]`/
   `[backtest]` actually constructing the screens, not by any test that only checks `contribute()`
   in isolation. Fixed by stashing `container` in `boot()` instead, whose `container` is the real
   one (every pre-existing `container.resolve(...)` call in these modules' own `boot()` bodies
   already depended on that being true).

   **Deliberately left alone, and why:** `AbstractScreenModule`/`ScreenRegistry.register_module()`
   themselves are not deleted, even though nothing in production calls them any more — `ScreenRegistry`
   itself (`register()`/`build_sidebar_navigation()`/`bind_to_router()`) stays the mechanism every
   screen, module-owned or shell-owned, ultimately renders through, and `register_module()`'s own
   unit coverage in `test_screen_registry.py` (~15 cases against a `_FakeModule` double) is real,
   passing coverage of a now-unused-in-production seam, not dead weight this step's own scope names.
   Retiring it is a separate, cleanly bounded decision (rewriting those ~15 tests too) left as a
   follow-up rather than folded into this PR.
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

   **PR 5.3 — the panel-contribution half itself rebuilt on the Engine's `ContributionRegistry`,
   landed 2026-09-19.** `shell/contribution_registry.py`'s `contribute()`/`panels()` now delegate
   identity/duplicate-checking, storage and render ordering to an internal
   `sagittarius_engine.extensions.pyside_mvc.runtime.ContributionRegistry`, retiring the hand-rolled
   copy of the same logic. What stayed app-side, and could not move: unknown-surface/place-not-accepted
   validation and the dev-mode gating check, both needing this app's own richer `Surface` (`owner`,
   `gated_by`) — the Engine's `SurfaceDeclaration` is deliberately narrower, by that file's own
   documented design (an app that needs gating keeps its own richer type and derives the narrower
   one, "not a reason to widen this type"). `Place`/`SizeHint` stay this app's own closed
   vocabularies; `_to_engine_descriptor`/`_from_engine_descriptor` translate at the boundary.
   Required bumping Elite's installed Engine to its current `main` (commit `72e4042`, carrying
   `TASK-043` E1/E2) first — done as a plain reinstall (`install-rule.md` §1 Option 1) since neither
   `requirements.txt` nor `pyproject.toml` pins an Engine version to edit; the user approved this
   explicitly before it ran. Zero behaviour change: all pre-existing tests pass unedited (45
   targeted + 420 architecture + 29 sanity + 4890 full `tests/unit`), `mypy` clean on 635 files via
   the CI-faithful invocation. `contribute_screen()`/`screens()`/`default_route()` are untouched —
   no Engine equivalent, that is `NavigationService`'s concern (PR 5.1).

   **PR 5.4 — the rendering side migrated onto the Engine's `RegionHost`, landed 2026-09-19.**
   `support/ui_kit/workbench_surface.py` (`WorkbenchSurface`) now inherits directly from the Engine's
   `sagittarius_engine.extensions.pyside_mvc.runtime.RegionHost`. The application `Place` vocabulary
   maps 1:1 to the Engine's closed `QMainWindow` physical layout anatomy (`RegionKind`). `accepts()`
   returns `frozenset[Place]`, satisfying both application `IPlaceHost` and Engine `IRegionHost`
   structurally because `Place(str, Enum)` members are `str` instances. `_environment_banner_factory`
   and `_add_environment_banner()` slot (`EPIC-021K`) are preserved intact. Overrides `_toolbar_top()`
   and `_toolbar_secondary()` set `::header` and `::context_bar` Qt object names to maintain full
   backwards compatibility with existing presenter `findChild` lookups. Method forwarders
   `place_widget()` and `show_modal()` catch and translate `EngineContributionError` to application
   `ContributionError`.
   Declared `RegionHost` in `src/infrastructure/engine_adapters/engine_capabilities.py` (`BOT-133`).
   Fixed deprecated import shim warning in `src/modules/backtesting/ui` (`LogListModel` imported
   directly from `sagittarius_engine.extensions.pyside_mvc`).
   Full verification: 24 tests passed in `test_workbench_surface.py`, 13 in `test_surface_building.py`,
   8 in `engine_adapters`, 29 in `test_composition_root.py` (all 10 navigable routes constructed clean),
   ruff/format clean, CI-faithful mypy clean across 635 source files, 418/419 architecture tests passed
   (single excluded worktree-path hyphen/underscore naming flake in `test_verify_against_base.py`).

   **PR 5.5 — retire `AbstractScreenModule` and dead `register_module()` seam, promote `INavigationService` DI integration, landed 2026-09-19.**
   Deleted `src/support/ui_kit/registry/abstract_screen_module.py`. Removed `register_module()` from
   `IScreenRegistry` (`src/support/ui_kit/registry/ports/i_screen_registry.py`) and `ScreenRegistry`
   (`src/support/ui_kit/registry/screen_registry.py`), removing the last traces of the legacy module
   registration seam left over from PR 5.2. Cleaned exports in `src/support/ui_kit/registry/__init__.py`.
   Refactored `tests/unit/support/ui_kit/registry/test_screen_registry.py` to replace `_FakeModule`
   with a clean `_make_descriptor()` builder, directly exercising `ScreenRegistry.register()` across all 12
   tests with zero mock module overhead.
   Advanced `NavigationService` integration: `MainWindow` now accepts optional constructor injection of
   `navigation_service: INavigationService | None = None` (falling back to building its own
   `NavigationService(self._router)` when omitted — a seam for tests, not a change to production
   boot behaviour) and exposes it via `@property def navigation_service`. `app_bootstrapper.py`
   registers `window.navigation_service` as a container singleton for `INavigationService` right
   after `MainWindow` construction, so any component or coordinator can navigate without a direct
   reference to `MainWindow` — registered only after boot's own initial `RESTORE` navigation has
   already run, so nothing can resolve it before it exists. New coverage in
   `tests/unit/presentation/ui/test_main_window_navigation.py`: one test proves the default-construction
   path builds a real `NavigationService`; the other injects a `Mock(spec=INavigationService)` and
   asserts it (not an internally-built instance) receives both the boot `RESTORE` call and a
   `switch_screen()`-triggered `USER_INTENT` call — a wiring test that fails if the injection were
   silently ignored, not a decorative one.

   **Correction, 2026-09-19 — the PR's own first verification claim was wrong, caught by independent
   review.** The commit that claimed to "auto-sort imports across 19 files in `scripts/`" actually
   moved each file's `sagittarius_engine.*` import to *after* the `Sagittarius_Elite_Warrior.*` block
   instead of before it, breaking `ruff`/isort's third-party-before-first-party grouping the base tree
   already had correct — so `ruff check src tests tools scripts` was red on GitHub Actions
   (`FAILED_STEPS: Ruff Lint`) on the exact commit whose own PR body said "PASS (0 errors)". Caught by
   an independent reviewer session cross-checking the claim against a properly-isolated `git worktree`
   (named to match the repo, per `CS-006`/`test_verify_against_base.py`) rather than trusting the
   citation, then confirmed against the real GitHub Actions log. Fixed by reverting those 19 files to
   their original, already-correct import order rather than re-attempting the sort — verified this
   time against the real log, not re-asserted: `ruff check`/`ruff format --check src tests tools
   scripts` clean; the 42 targeted tests above still pass; `tests/unit/architecture` **420 passed**
   (not 418 — the true count, matching the base commit exactly since no architecture test file is
   touched by this PR); CI-faithful `mypy` clean across 635 source files;
   `scripts/check_skill_prompt_references.py` OK, 39 documents. Also added a one-line correction to
   `Docs/SCREEN-REGISTRY-PATTERN/README.md`'s own status line, which still described
   `AbstractScreenModule`/`register_module()` as living example code after this PR deleted them.
3. Every new Engine API is declared in `engine_capabilities.py` (`BOT-133`). `ContributionRegistry`
   and `RegionHost` capabilities are both declared.
4. The Engine's screen conformance suite runs against **every** surface of this application (PR 5.6).
   **Deferred, 2026-09-19 — closed out of this phase's scope by user decision.** Not achievable from
   Elite alone: the suite is bundled into `Sagittarius_Engine`'s own `TASK-043` E3, which has not
   started on the Engine side (verified in that repository's checkout, not assumed). Tracked there,
   not duplicated here (`ONBOARDING.md` §9) — a future session revisits this item once E3 lands.

## 2. Done when

- `main_window.py` imports no screen; navigation is built entirely from self-description. **Verified
  2026-09-19**, not narrated: `grep -n "^from\|^import" src/presentation/ui/main_window.py` names no
  screen module, matching the file's own docstring ("this shell knows no concrete screen").
