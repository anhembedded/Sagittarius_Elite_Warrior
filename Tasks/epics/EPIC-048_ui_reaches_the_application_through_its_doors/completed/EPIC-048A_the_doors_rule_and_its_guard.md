# EPIC-048A — The rule for the UI's doors is written, and a guard that only shrinks holds it

**Status:** ✅ Done (2026-10-24)
**Source:** the owner's delegation of 2026-10-24 (*"các quyết định, bạn thay tôi quyết định phù hợp tất cả hiến pháp"*, "decide them for me, consistent with the whole Constitution"), settled as G9 of the EPIC-047 charter; the [decision record](../DECISION_2026-10-24_the_ui_reaches_the_application_through_its_doors.md) D1–D4.
**Risk:** 🟡 — a guard that scans 441 files and imports modules can be slow or flaky, and a wrong classification either blocks work or lets bypasses in.
**Complexity:** M — one rule section and one test with a baseline file; the method exists as a spike.
**Epic:** [EPIC-048](../README.md)
**Depends on:** None

---

## 1. Context and problem
`architecture-rule.md` §3 says a module imports another only through its `contracts/`, and says nothing about how the UI reaches the application. De-risk R7 (DERISK §7.3, at `5ddbd68`) found **215 imports in 82 files over 18 screen areas** that reach application services, application internals, adapters or behavioural ports outside the doors, and **30 functions under `ui/` that take the whole `IContainer`**. Nothing stops a 216th. EPIC-047 cannot put a remote backend behind a screen that bypasses the doors.

## 2. Acceptance criteria
- [x] `.claude/rules/architecture-rule.md` states the rule of ADR D1: the UI reaches the application through `ICommandDispatcher`, `IEventPublisher` and `IEventBus`, plus the UI-only allowlist (`INotifier`, `IRealMoneyConsent`, `IThreadManager`, `IInstanceAccess`, `IDisplayTimezonePreference`, `IDisplayPreferences`) and the pure-code ports `IBotKind`, `IBotKindCatalog` and `ICandleFeed`; the section carries its `[guard: …]` tag, and `python3 scripts/check_skill_prompt_references.py` passes.
- [x] A test in `tests/unit/architecture/` reads the UI tree with DERISK §7.2's method and compares each area's counts (`APP_SERVICE`, `APP_OTHER`, `ADAPTER`, `PORT`, split `fn` and `data`) and the count of functions that take `IContainer` with a committed baseline file.
- [x] The first baseline is **measured by this task**, not copied: it starts from R7's 215 imports, 82 files and 30 container-taking functions less the 18 imports the allowlist now admits (197 expected). The task records the measured numbers and any difference from R7 in its Implementation notes.
- [x] The guard fails when a count rises, and fails with a message that names the file, the imported name and its class. A count that falls fails until the baseline is lowered in the same pull request (a ratchet, `P8`).
- [x] Mutation check (`testing-rule.md`): a planted new application-service import in a UI file turns the guard red; removing an existing one without lowering the baseline turns it red; both revert green.
- [x] The guard runs in the full gate in a time the task records, and creates no stray file or `ResourceWarning`.
- [x] `data` imports are a second baseline line (ADR D4); a new `fn`, port or adapter import fails at once.

## 3. Design
The guard mirrors the repository's own baseline guards (`tests/unit/architecture/baseline_*.txt`, `test_module_boundaries.py`) and the spike `scan_ui_doors.py` of DERISK §7.2 (`ast` plus `importlib`): the classification, the `USE_CASE_MESSAGE` pattern and the `IContainer` parameter check come from there. The allowlist lives in one place the guard and the rule both name (`P3`); the rule cites the file and does not repeat the names where a copy would drift. The baseline file holds counts per area, not file lists, so an unrelated import rename does not churn it. Pure-code ports are allowed because they are code or public data, not host facts (ADR D2).

## 3a. Reuse
Checked `.claude/rules/capabilities.md` and `tests/unit/architecture/`: `scanned_roots_registry.py`, `screen_files.py` and `guard_scan_resolver.py` may already list the UI roots; `used` if they do, with the file named in the notes; `not used because …` otherwise. The spike is the starting point, not a dependency.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `.claude/rules/architecture-rule.md` | the rule text (new subsection under §3) with its guard tag |
| `tests/unit/architecture/test_ui_reaches_the_application_through_its_doors.py` | the guard (name proposed) |
| `tests/unit/architecture/baseline_ui_doors.json` | the counts per area, the container count (name proposed) |
| `.claude/README.md` | the manifest row if the rule file's description changes |

## 5. Testing
Tier: architecture guard, in the unit tier (`ci-rule.md` §2). Each acceptance item maps to the guard itself and to the mutation check above, run by hand and recorded with the red and green output. The full gate's job log is read for `FAILED|ERROR|Traceback|ResourceWarning`. Not run.

## 6. Docs touched
`.claude/rules/architecture-rule.md` (new §3.1). `Docs/VOCABULARY/README.md`: the entry "The UI's doors". `.claude/README.md`: unchanged, the rule file's description did not change. No `Docs/MODULES/` file: no module's code changed.

## Implementation notes (written when done)
**What shipped.** The rule is `architecture-rule.md` §3.1 ("The UI's doors"), three bullets each tagged `[guard: test_ui_reaches_the_application_through_its_doors.py]`: the rule, the allowlist line, the baseline. The guard is `tests/unit/architecture/test_ui_reaches_the_application_through_its_doors.py`; the scan is `tests/unit/architecture/ui_doors_scan.py` (R7's `classify`, `USE_CASE_MESSAGE` and container check, split out to keep both files short); the counts are `tests/unit/architecture/baseline_ui_doors.json`.

**Decisions taken.**
- *One list (P3).* The allowlist is written once, on the rule's line that opens `**The doors and the allowlist.**`; `ui_doors_scan.allowlist()` reads the backticked names from it. A second test fails when that line stops naming the three doors, or names a class that exists under no `contracts` package of `src/` and not in the engine's `interfaces` package.
- *Two allowlist names dropped.* `IDisplayTimezonePreference` and `IDisplayPreferences` (ADR D1, R7 §7.2) name no class anywhere in `src/` or the engine at `96cb27c`: the display time zone is read through `support/ui_kit/services/display_timezone_preference.py`, which is not a `contracts` package and so is never counted. They allowed nothing; listed, they would pre-approve any future class of that name without a review. The rule's line leaves them out, and the real-contract test keeps a phantom name from coming back. No count changes.
- *Relative imports resolved.* R7 read absolute imports only; 369 relative imports exist under `ui/`, two of them leaving `ui/` (`backtesting/ui/coordinators/monte_carlo_coordinator.py` → `...contracts`). The scan resolves each against the file's package, so `from ...application.services import x` cannot go round the guard. Measured: no extra hit today.
- *An exception class is data.* R7's split counted `UnknownBotsError` (`bots/application/plan/plan_export.py`, caught by `plan_export_flow.py`) as data; the scan does the same (`issubclass(obj, BaseException)`), which reproduces R7's 32 `fn` / 78 `data` exactly.
- *Baseline shape (ADR D4).* Three sections, per screen area and per class: `around_the_doors` (`APP_SERVICE_fn`, `APP_OTHER_fn`, `ADAPTER`, `PORT`), `application_data` (`APP_SERVICE_data`, `APP_OTHER_data`) and `takes_the_container` (`CONTAINER`). Every count is exact: a rise fails with every hit of that area and class (file, imported name, class); a fall fails until the entry is lowered (the shape of `test_god_files_only_shrink.py`).

**Reuse (§3a).** `ui_trees.py` (`UI_TREES`) lists five of the seven `modules/*/ui` roots, so not used; `screen_files.py`'s `screen_roots()` globs `modules/*/ui` but adds `shell/`, which is not a module's UI, so not used; the scan globs `src/modules/*/ui/**/*.py` itself. `guard_scan_resolver.py` cannot read an imported root, so the guard is named in `test_guard_scans_its_registered_root.py`'s `_UNRESOLVABLE_GUARDS`, and its row is in `scanned_roots_registry_module_dependencies.py` (the main registry is at the 400-line ceiling).

**The measured baseline, at `96cb27c`.**

| Measurement | R7 (`5ddbd68`) | Measured here |
| :--- | :-: | :-: |
| Files scanned | 441 | 441 |
| R7's own allowlist and method: imports / files / areas | 215 / 82 / 18 | 215 / 82 / 18 |
| fn / data of the 110 application imports | 32 / 78 | 32 / 78 |
| Container-taking functions | 30 | 30 |
| With `IBotKind`, `IBotKindCatalog`, `ICandleFeed` allowed: imports / files / areas | 197 expected | **197 / 73 / 16** |
| Of the 197: `PORT` / `APP_SERVICE` fn, data / `APP_OTHER` fn, data / `ADAPTER` | — | 85 / 12, 16 / 20, 62 / 2 |
| `around_the_doors` / `application_data` / `takes_the_container` | — | **119 / 78 / 30** |

The two areas that leave the count are `bots/ui/backtest` and `bots/ui/chart` (their only hits were the pure ports); `market_data/ui/settings` appears in the baseline for its two container-taking functions only. `bots/ui/bots_screen` reads 20 around the doors (10 service `fn`, 8 ports, 2 adapter), 15 data, 4 container functions.

**Mutation checks (by hand, each reverted).**
1. A planted `from ...bots.application.services.readiness.resume_readiness import assess_resume` in `src/modules/trading/ui/trade/__init__.py` → `test_no_count_around_the_doors_rises` red: `around_the_doors / trading/ui/trade / APP_SERVICE_fn: 0 -> 1` followed by `src/modules/trading/ui/trade/__init__.py: Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.resume_readiness.assess_resume (APP_SERVICE_fn)`; reverted, `6 passed`.
2. The `bots.adapters.plan_file` import removed from `src/modules/bots/ui/bots_screen/plan_export_flow.py` → `test_a_count_that_fell_is_lowered_in_the_baseline` red: `around_the_doors / bots/ui/bots_screen / ADAPTER: 2 -> 0`; reverted, `6 passed`.
3. `IDisplayTimezonePreference` and `IDisplayPreferences` on the rule's line → `test_every_allowlisted_name_is_a_real_contract` red, naming both.

**Run time.** About 3 s alone (`--durations`: 2.96 s in the module fixture, which imports the classified modules; every test after it under 0.1 s); the same imports are already loaded in the full gate. Read-only, writes no file. No `ResourceWarning` in the architecture suite's log.

**Verification at this commit.** `pytest tests/unit -q -n auto` (the architecture suite included): 19296 passed, 2 skipped (log read for `FAILED|ERROR|Traceback|ResourceWarning`: none). Commit tier `ci-local.ps1 -SkipTests`: `RESULT: PASS`, log read the same way. The full gate is the PR's GitHub Actions run.
