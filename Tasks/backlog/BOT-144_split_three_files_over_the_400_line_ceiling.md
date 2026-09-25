# BOT-144 — Four files split back under the 400-line ceiling

**Status:** 🔵 Backlog
**Source:** Independent PR review of `PR #257` (2026-09-23), flagged as a should-fix, pre-existing item — "worth a tracked follow-up task rather than continuing to accrete onto these three files indefinitely." A fourth file (`paper_exchange.py`) was added from an independent review of `PR #266` (2026-09-25), same finding, different file.
**Risk:** 🟡 — each file is a live Presenter/Panel wired into the composition root and covered by hundreds of existing tests; a split done as extraction (not rewrite) should be behavior-preserving, but a bad seam could silently drop a signal connection or FSM transition.
**Complexity:** L — three separate god-files, each needing its own extraction design; no single mechanical transform covers all three.
**Epic (optional):** None — standalone debt-paydown, not tied to a feature epic.
**SPEC (optional):** None.
**Depends on:** None.

---

## 1. Context and problem

`architecture-rule.md` §5.4 sets a hard split threshold: **>400 lines per file** (`[review: C7, D6, D7]`). Three files this repository actively edits are 2.5–5x over it, and every recent feature PR through the Dev Board or Data Management screens adds more to them rather than splitting:

- `src/modules/trading/ui/dashboard/dashboard_presenter.py` — **1994 lines** (measured 2026-09-23; was 1975 before `PR #257`, 1994 after).
- `src/modules/trading/ui/dashboard/dev_board_panel.py` — **1145 lines** (was 1070 before `PR #257`).
- `src/modules/market_data/ui/data_management_presenter.py` — **964 lines** (was 861 before `PR #257`).
- `src/modules/backtesting/domain/paper_exchange.py` — **587 lines** (measured 2026-09-25, `BOT-105C`; was 460 after `PR #266`'s `StopManagementPolicy` extraction, before that PR's Trailing Stop addition it was 507. `BOT-105C` added `_close_partial_position()`/`_apply_partial_take_profits()` for Partial Take Profit — a "books" mechanism, same abstraction level as `_close_one_position()`, so it was deliberately kept alongside it rather than routed into `StopManagementPolicy` [which only ever adjusts pre-fill risk state, never touches `self._balance`/`self._trades`]. What is left — `_open()`/`_close()`/`_close_one_position()`/`_close_partial_position()`/`_apply_partial_take_profits()`, the whole entry/exit/trade-recording lifecycle — is well-tested and was deliberately left as one extraction target rather than risking a large refactor inside a feature PR, same reasoning `PR #266` already applied here).

This is not new debt from any one PR — `EPIC-003` (Presenter/god-file decomposition) already extracted several coordinators out of two of the first three files, but stopped short of bringing either under the ceiling, and no machine guard currently catches a file that is already over 400 lines from growing further (`C7`/`D6`/`D7` are review-only checks per `architecture-rule.md`, not a pytest guard like the module-boundary allowlist or the app-styling ratchet).

## 2. Acceptance criteria

- [ ] `dashboard_presenter.py`, `dev_board_panel.py`, `data_management_presenter.py` are each ≤400 lines, achieved by extracting cohesive responsibilities into new coordinator/helper classes under the same module's `ui/` tree — mirroring the existing coordinator pattern (`GapCoordinator`, `IndicatorCoordinator`, `ExportImportCoordinator`, etc.), not by deleting functionality or renaming without moving logic.
- [ ] `paper_exchange.py` is ≤400 lines, achieved by extracting its remaining position entry/exit lifecycle (`_open()`/`_close()`/`_close_one_position()`/`_close_partial_position()`/`_apply_partial_take_profits()`) into a domain policy under `domain/policies/`, mirroring the extraction `PR #266` already did for `StopManagementPolicy`.
- [ ] Every existing test for these three files (and their coordinators/view models) still passes unchanged in behavior — a test may need its constructor call updated for a new collaborator, but must not need its assertions weakened.
- [ ] No FSM transition, signal connection, or coordinator wiring present before the split is silently dropped — verified by running the full `tests/unit` suite plus a manual `tools/run_app` (or `scripts/run-dev.ps1`, whichever this repo's `run` skill uses) smoke pass on the Dev Board and Data Management screens.
- [ ] A machine guard is added (or an existing one extended) so a file already over 400 lines cannot grow further without the gate failing — closing the gap the independent review noted ("no guard test currently catches this"). A shrink-only ratchet, mirroring `test_app_styling_only_shrinks.py`'s own pattern, is the vetted precedent to apply before inventing a new mechanism.

## 3. Design

{Not designed yet — this is a backlog entry recording the problem and its acceptance bar, not a committed extraction plan. Whoever picks this up should first read each file's own history (`git log -p`) and `EPIC-003`'s README for what has already been tried/rejected for these exact files, then measure a concrete cut (which methods/fields move where) the same way `EPIC-025`'s own PRs measured every move before executing it, rather than guessing a split boundary.}

## 4. Changes, per file

{To be filled in once a concrete extraction plan exists for each of the three files — likely three separate PRs given the "one coordinator, one job family" convention already established, one per file rather than one PR touching all three at once.}

## 5. Testing

{Map each acceptance criterion to a test once the extraction plan exists. The new shrink-only line-count guard is itself the test for acceptance criterion 4; criteria 1–3 are verified by the full `tests/unit` suite plus the manual smoke pass criterion 3 names.}

## Resume (optional; while unfinished)

Not started. Next executable action: pick one of the three files (recommend starting with `data_management_presenter.py` at 964 lines — the smallest gap to the ceiling, and the newest of the three post-`EPIC-025` moves, so its extraction seams are freshest), read its full history and current coordinator split, and write a concrete §3 Design + §4 Changes plan before touching code.
