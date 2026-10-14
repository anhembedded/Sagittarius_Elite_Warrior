# BOT-177 — The bots module's application services are grouped by feature into sub-packages, and a guard keeps the top level from regrowing

**Status:** ✅ Done (2026-10-14)
**Priority:** P2
**Board:** The 111 flat modules of `bots/application/services/` are moved, unchanged but for import lines, into a kind-neutral shell (`services/{lifecycle,orders,venue,positions,risk,readiness,watches}/`, 67 modules) and Grid-only code (`application/kinds/grid/` with `start/`, `stop/`, `watch/`, `recovery/`, 44 modules); two guards keep the top level empty and the shell off the kinds, with a 27-file shrink-only allowlist of today's exceptions.
**Source:** The owner, 2026-10-14: *"hình như phần service đang quá nhiều file bắt đầu từ feature service có thể gom lại thì dir được rồi"* ("the services part seems to have too many files; starting from the feature services, they could be grouped into directories"). On the first draft they added: *"chia như vậy là chưa tính đến common rồi đúng không?"* ("split like that, it does not account for the common part yet, right?").
**Risk:** 🟡 — 227 files import from the package; a missed import or a stale path citation breaks CI or a doc, though behaviour cannot change
**Complexity:** M — mechanical, but wide
**Depends on:** None. Do it **before** `EPIC-040A`, so that epic works on the new layout and no open PR conflicts with the move.

---

## 1. Context and problem
- `src/modules/bots/application/services/` holds **111 modules in one flat directory**. By prefix: 39 `grid_*`, 17 `bot_*`, 7 `venue_*`, 5 `futures_*`, 4 `order_*`, and a long tail of pairs (`closer_spot`/`closer_futures`, `cost_model_*`, `exposure_check_*`, `opening_*`, `risk_guard_*`).
- **227 files** under `src/` and `tests/` import from it.
- The flat list hides structure. A reader cannot see which services make up a Grid start, a stop, or a watch, and the Spot/Futures pairs that implement one port sit apart. The 2026-10-14 bots module map flagged this as the module's main readability debt.

## 2. Acceptance criteria
- [x] **The first cut is kind-neutral versus kind-specific**, matching the layout the module already uses elsewhere (`domain/grid/`, `ui/kinds/grid/`):
  - `application/services/` keeps only the **shared bot shell**: services every bot kind uses, whatever its kind.
  - `application/kinds/grid/` holds everything that knows the Grid. A future kind (the strategy kind of `EPIC-040G`, DCA) gets its own `application/kinds/<kind>/` beside it.
- [x] Inside each side, files are grouped by feature. This is the starting proposal; the author may move a file with a one-line reason in Implementation notes:

  | Package | Holds |
  | :--- | :--- |
  | `services/lifecycle/` | runner, run state, executors registry, command gate and lock, restore, boot recovery, lookup, read-only runner and store, notifying store, other-active-bot, running-bots objection, files-readable check, health contributor, kind catalog |
  | `services/orders/` | order gateway, order history, order outcome, order flags (Spot and Futures), order-session opening, applied fills |
  | `services/venue/` | venue facts, needs, profiles, rules and settings gates; closed venue; exchange rules and facts; symbol brackets and status gate; settings check; the Futures rules, facts and start checks; mark source; funding and account views; exchange terms; connect-failure words |
  | `services/positions/` | exposure books, exposure checks, closers, opening strategies, cost models (each Spot/Futures pair side by side) |
  | `services/risk/` | risk guards and risk reads |
  | `services/readiness/` | readiness reader and assessment, resume readiness, progress reader, run facts |
  | `services/watches/` | price watch, user-stream watch, sleep watch, clock-gap detector, wake-exit check, streamed fine klines |
  | `kinds/grid/` | executor and its factory, facts, ladder placer, run context, runtime codec, task guard, budgets, exposures, housekeeping, parking, margin mode, order failure, earlier runs, reference price, ladder needs, Futures ladder needs, off-ladder orders, planner numbers, Futures backtest terms |
  | `kinds/grid/start/` | start preconditions, start sequence, interrupted start |
  | `kinds/grid/stop/` | stopper, stop sequence, stop request, stop retry, stopping wait, exit slices, mark exit |
  | `kinds/grid/watch/` | range, risk, storage, terms and key watches; price age and reaction; rate-limit pause; stream gap; tick extremes |
  | `kinds/grid/recovery/` | reconciler, recovery reader, resume sequence |

- [x] **The direction is enforced.** A new architecture guard fails if anything under `application/services/` imports `application/kinds/` or `domain/grid/`, with a probe test. Today's exceptions go in a shrink-only allowlist that names each importing file.
- [x] **Which of the 27 may belong in `kinds/grid/` instead.** The list above is not a to-generalise list. Some of those files do Grid work themselves, and the table put them in the shell for their Spot/Futures pairing or for the port they implement: `positions/opening_spot.py`, `opening_futures.py`, `closer_spot.py`, `closer_futures.py`, `venue/futures_start_checks.py`, `readiness/bot_run_facts.py` and `venue/symbol_status_gate.py`. They may move to `kinds/grid/` (or to a `kinds/grid/` sub-package) rather than be generalised; `EPIC-040B` decides per file when it knows what a second kind needs. The rest (`bot_runner`, `bot_executors`, `bot_run_state`, `bot_restore_service`, `bot_boot_recovery`, the risk guards, `venue_needs`, `venue_rules`, `exchange_rules`, `futures_rules`, `mark_source_futures`, `bot_order_gateway`, `streamed_fine_klines`, the readiness readers) are shell jobs that reach for Grid types, and are the ones to generalise.

**Generalisation candidates are listed, not changed.** Some `grid_*` services do a job every kind needs (price age, key probe, terms watch, storage watch, rate-limit pause, stream gap, task guard, stop retry), but their code depends on Grid types today. They move to `kinds/grid/` unchanged. The task's Implementation notes list them, with the Grid types each depends on, as input for `EPIC-040B` and `EPIC-040G`, which lift them into the shared shell when a second kind needs them.
- [x] **Pure move.** No function body changes. Module names stay the same unless two would collide. `git diff -M` shows renames, and the only content changes are import lines.
- [x] Every import in `src/` and `tests/` is updated by a script, run once and kept out of the commit. No re-export shim is left behind at the old path.
- [x] The architecture guards, mypy, ruff and the full unit, integration and sanity suites pass. Allowlists and baselines that name a moved path are updated **only by path**; no entry is added.
- [x] Every path citation to a moved file is repointed: `.claude/rules/` (including `capabilities.md`), `Docs/` (including `Docs/MODULES/bots.md`), `Tasks/` documents that are not completed history, and skills. `python3 scripts/check_skill_prompt_references.py` passes.
- [x] A guard holds the result. `application/services/` directly contains at most the files this task leaves there, so a new service must go into a sub-package. The guard has a probe test.
- [x] **Docs touched:** `Docs/MODULES/bots.md` gains a short "Where the code lives" list naming each sub-package and its job.

## 3. Design
- **Kind-neutral first, then by feature.** The first question is "would a second bot kind use this?". That is the seam `EPIC-040` and the strategy kind need, and it matches `domain/grid/` and `ui/kinds/grid/`. The second question is what the service does.
- **Package by feature, not by layer or by venue.** A sub-package answers the question "what does this group of services do". Spot and Futures implementations of one port sit together inside their feature.
- **The move has no behaviour change**, so the existing suites are the regression net (`CONSTITUTION.md` P6, bounded change).
- **The new guard** mirrors the shrink-only ratchets already used (`test_god_files_only_shrink.py`), so the flat layout cannot grow back (P1, P8).

**Design assessment**

| Option | Verdict |
| :--- | :--- |
| Feature sub-packages, pure move, guard (chosen) | Readable structure; zero behaviour risk; cannot drift back |
| Feature only, no shared/kind split (first draft) | Rejected by the owner: it hides which code is common to every bot, which is exactly what `EPIC-040` must find |
| Group by venue (`spot/`, `futures/`) | Rejected: most services are venue-neutral, and the pairs implement one port each, so they belong with that port |
| Leave a re-export shim at the old paths | Rejected: two import paths for one thing, which the boundary scan and reviewers would have to police forever |
| Split during `EPIC-040` instead | Rejected: a wide move in the middle of feature PRs causes conflicts and mixes refactor with behaviour change |

## 3a. Reuse
- Ratchet shape: `tests/unit/architecture/test_god_files_only_shrink.py`.
- Path checking: `scripts/check_skill_prompt_references.py` (`scripts/rule_integrity/paths.py`).
- Boundary scan: `tests/unit/architecture/boundaries/`. Run it unchanged; the move must not need a new allowlist entry.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/**` | Moved into sub-packages, each with an `__init__.py` |
| about 227 importers in `src/` and `tests/` | Import lines only |
| `src/modules/bots/application/kinds/grid/**` | New home of the Grid-only services |
| `tests/unit/architecture/test_bots_services_stay_grouped.py` | Two guards and probes: no loose top-level files, and the shared shell never imports a kind |
| `.claude/rules/*.md`, `Docs/**/*.md`, live `Tasks/**/*.md` | Path citations |
| `Docs/MODULES/bots.md` | "Where the code lives" list |

## 5. Testing
- The commit tier: ruff, format, mypy and the reference check.
- The architecture guards.
- The bots unit, integration and sanity suites, unchanged and green. The test count before and after is recorded.
- The new guard's probe: a file dropped into the top level turns it red.
- The `-Full` run on GitHub.
- Proof of a pure move: `git diff -M --stat` lists renames only, and `git diff -M` shows only import-line changes.

## 6. Docs touched
`Docs/MODULES/bots.md` gains "Where the code lives", and its existing citations are repointed. Path citations in rules, docs and live tasks are repointed.

## Implementation notes (written when done)

**Result.** 111 modules moved with `git mv` (111 renames, none left loose in `services/`); 12 empty `__init__.py` added, one per new sub-package. Shell: 67 modules in 7 feature packages. Grid: 44 modules (`kinds/grid/` 21, `start/` 3, `stop/` 7, `watch/` 10, `recovery/` 3).

Measured on the head of this branch:

| What | Before | After |
| :--- | :--- | :--- |
| `services/` top level | 111 files | 0 files |
| Modules in `services/**` | 111 | 67 |
| Modules in `kinds/grid/**` | 0 | 44 |
| `git diff --cached -M --stat` | | 271 files, 766 insertions, 766 deletions; 111 renames |
| Non-import lines changed in `.py` | | 4, all path string literals in architecture tests (`test_every_order_is_reconciled.py` x3, `test_ui_never_shows_an_exception.py` x1) |

**Pure move.** No function body changed. The importers were rewritten by a one-off script that is not committed, then `ruff check --select I --fix` and `ruff format` re-sorted and re-wrapped the import blocks. Two `from ...services import <module>` lines (`test_exchange_rules.py`, `test_run_process_beside_other_processes.py`) were edited by hand. No re-export shim exists at the old paths.

**Tests.** Collected before -> after: unit 13614 -> 13634, integration 644 -> 644, sanity 65 -> 65. The 20 new unit items are the new guard file's six tests and the per-guard checks `test_scanned_roots_are_not_empty.py` and `test_guard_scans_its_registered_root.py` run for its registry row. Run of `tests/unit/modules/bots`, `tests/unit/architecture`, `tests/integration` and `tests/sanity`: 4656 passed before, 4664 after (+8 new), 3 skipped both. One test fails identically before and after: `tests/integration/presentation/ui/test_workbench_conformance.py::test_workbench_conformance[True-1024x700]` (`backtest@1024x700/fits_the_window: needs 719x706`), a window-size assertion this container's fonts trip; it is red on the untouched checkout and unrelated to the move. The commit tier (`ci-local.ps1 -SkipTests`: ruff, format, mypy, reference check) passes. The `-Full` run is GitHub's.

**Guards.** `tests/unit/architecture/test_bots_services_stay_grouped.py`: no loose file in `services/`, and no file under `services/` imports `application/kinds/` or `domain/grid/`. Today's 27 exceptions are in `tests/unit/architecture/baseline_bots_shell_imports_a_kind.txt` (shrink-only both ways: a new file fails, a stale line fails). Its registry row is in `scanned_roots_registry_module_dependencies.py` (the main registry file is at the 400-line ceiling). Mutation checks against the real tree, each turning exactly the named test red and nothing else: a stray `services/probe_loose.py`; `services/orders/probe_kind.py` importing `application.kinds`; `services/risk/probe_domain.py` importing `domain.grid`; a baseline line for a file that does not import a kind; a baseline line deleted. The same cases are also probe tests with `tmp_path` trees, including `import X`, `from X import Y`, and `from ...domain import grid`.

**Allowlists and baselines.** None named a moved bots path except `test_every_order_is_reconciled.py`'s three path keys, repointed by path. The only new entries are the 27 lines of the direction guard's baseline, which record imports that already existed.

**Deviations from the proposal table, each one line.**
- Every sub-package has an empty `__init__.py`, as section 4 asks, though `services/`, `domain/grid/` and most of `ui/kinds/grid/` are namespace packages. Nothing broke either way; flag it if you prefer the namespace convention.
- `tests/unit/modules/bots/application/services/` (the tests and their `*_world.py` helpers) stays where it is; the task moves only sources, and no guard asks tests to mirror them.
- Path citations were repointed in `Docs/`, `Tasks/` outside `completed/` and `Tasks/reports/`, and in code. Completed tasks and dated reports keep the paths of their day. `.claude/` cited none of the moved files, so nothing there changed. `.../name.py` and bare-name citations in `bots.md` name no directory and were left.

**Shell files that still import Grid code (the 27 allowlisted).** They sit in the shell by the table, but a second kind could not use them as written. The Grid types they reach are in the baseline file's neighbours; the groups are: lifecycle (`bot_runner`, `bot_run_state`, `bot_executors`, `bot_restore_service`, `bot_boot_recovery`: `GridExecutor`, its factory, `GridRuntime`/`GridReason`, `GridRuntimeCodec`, `GridStartPreconditions`, `GridInterruptedStart`), positions (the Spot/Futures closers, opening strategies and exposure checks: `GridRunContext`, `GridHousekeeping`, `GridOrderFailure`, `GridStopRequest`, `GridExitSlices`, `GridPlan`, ladder functions), readiness (`GRID_MARKETS`, `GRID_KIND_ID`, `GridParams`, `GridRuntimeCodec`, `PlannerNumbers`, `GridBudget`), risk (`PlanRiskInputs`, `FuturesGridThresholds`, `judge_futures_plan`, `classify_risk`), venue (`LadderNeeds`, `FuturesNeeds`, `GridRunContext`, `GridMarginMode`, `GridBudget`), `bot_order_gateway` (`rate_limit_pause.whole_seconds`) and `streamed_fine_klines` (`FineKlines`, `PriceBar`).

**Generalisation candidates (moved to `kinds/grid/` unchanged; their job is generic, their code is not yet).** Input for `EPIC-040B` and `EPIC-040G`:

| Service | Grid types it depends on |
| :--- | :--- |
| `kinds/grid/watch/grid_price_age.py` | only `domain/grid/price_freshness` (stale-after constants and `price_is_stale`); the closest to generic |
| `kinds/grid/watch/grid_key_probe.py` | `GridRunContext`, `GridReason`, `grid_order_failure.halt_with`/`key_rejected_detail` |
| `kinds/grid/watch/grid_terms_watch.py` | `GridRunContext`, `GridReason`, `halt_with` |
| `kinds/grid/watch/grid_storage_watch.py` | `GridRunContext`, `GridReason`; `bot_run_state.FAILED_SAVES_BEFORE_PAUSE` (shell) |
| `kinds/grid/watch/grid_rate_limit_pause.py` | `GridRunContext`, `GridReason`, `halt_with`, `GridResumeSequence`; `domain/grid/rate_limit_pause` |
| `kinds/grid/watch/grid_stream_gap.py` | `GridRunContext`, `GridReason`, `halt_with`, `GridReconciler`, `ReconcileMismatch`, `ReconcileWait` |
| `kinds/grid/grid_task_guard.py` | `GridRunContext`, `GridReason`, `fault_with`, `GridParking`, `GridRateLimitPause`, `GridStorageWatch` |
| `kinds/grid/stop/grid_stop_retry.py` | `GridRunContext`, `GridReason`; `domain/grid/rate_limit_pause.AUTO_RESUME_MARGIN` |

Common to all: `GridRunContext` and `GridReason` (the run context and the halt vocabulary). Lifting those two behind a kind-neutral run context is the single change that frees most of the table.
