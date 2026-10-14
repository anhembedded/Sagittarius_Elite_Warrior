# BOT-177 — The bots module's application services are grouped by feature into sub-packages, and a guard keeps the top level from regrowing

**Status:** 🔵 Backlog
**Priority:** P2
**Board:** `bots/application/services/` (111 flat files) is split into a kind-neutral bot shell (`services/`, grouped by feature) and Grid-only code (`application/kinds/grid/`), as a pure move with no behaviour change, guarded in both directions, before `EPIC-040` starts editing them.
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
- [ ] **The first cut is kind-neutral versus kind-specific**, matching the layout the module already uses elsewhere (`domain/grid/`, `ui/kinds/grid/`):
  - `application/services/` keeps only the **shared bot shell**: services every bot kind uses, whatever its kind.
  - `application/kinds/grid/` holds everything that knows the Grid. A future kind (the strategy kind of `EPIC-040G`, DCA) gets its own `application/kinds/<kind>/` beside it.
- [ ] Inside each side, files are grouped by feature. This is the starting proposal; the author may move a file with a one-line reason in Implementation notes:

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

- [ ] **The direction is enforced.** A new architecture guard fails if anything under `application/services/` imports `application/kinds/` or `domain/grid/`, with a probe test. Today's exceptions go in a shrink-only allowlist that names each importing file.
- [ ] **Generalisation candidates are listed, not changed.** Some `grid_*` services do a job every kind needs (price age, key probe, terms watch, storage watch, rate-limit pause, stream gap, task guard, stop retry), but their code depends on Grid types today. They move to `kinds/grid/` unchanged. The task's Implementation notes list them, with the Grid types each depends on, as input for `EPIC-040B` and `EPIC-040G`, which lift them into the shared shell when a second kind needs them.
- [ ] **Pure move.** No function body changes. Module names stay the same unless two would collide. `git diff -M` shows renames, and the only content changes are import lines.
- [ ] Every import in `src/` and `tests/` is updated by a script, run once and kept out of the commit. No re-export shim is left behind at the old path.
- [ ] The architecture guards, mypy, ruff and the full unit, integration and sanity suites pass. Allowlists and baselines that name a moved path are updated **only by path**; no entry is added.
- [ ] Every path citation to a moved file is repointed: `.claude/rules/` (including `capabilities.md`), `Docs/` (including `Docs/MODULES/bots.md`), `Tasks/` documents that are not completed history, and skills. `python3 scripts/check_skill_prompt_references.py` passes.
- [ ] A guard holds the result. `application/services/` directly contains at most the files this task leaves there, so a new service must go into a sub-package. The guard has a probe test.
- [ ] **Docs touched:** `Docs/MODULES/bots.md` gains a short "Where the code lives" list naming each sub-package and its job.

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
