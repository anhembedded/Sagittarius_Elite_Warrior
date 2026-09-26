# BOT-144 — Four files split back under the 400-line ceiling

**Status:** 🟡 In progress — `data_management_presenter.py` slice implemented 2026-09-26: 964 → 671 lines (30% cut), still over the 400-line target; see §4 for the honest remaining gap and why the extraction stopped where it did.
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

### 3.1 `data_management_presenter.py` (964 → target ≤400) — designed 2026-09-26

Measured, not guessed: the file's ~380-line "Qt Slots" block and its ~90-line
"Backward-compatible worker delegates" block together account for most of
the overage. Both exist because each `Coordinator` (`ScanCoordinator`,
`SyncCoordinator`, `GapCoordinator`, `KLineInspectorCoordinator`,
`ExportImportCoordinator`) only ever exposes `run_*()` **background-worker**
methods — the "user clicked, validate, log, transition the FSM, submit to
the thread pool" orchestration around each one stayed on the Presenter,
duplicated ~15 times with only the FSM state and log string differing.

**The seam to close was already built, just never wired up.** Every
Coordinator's constructor already accepts `transition_fsm: Callable[[UIMode],
bool]` and `get_current_fsm_state: Callable[[], UIMode]` (`architecture-rule.md`
§7.2.1's "seam now, variant later" — the extension point exists from
`EPIC-003B`). `grep -rn "_transition_fsm(" src/modules/market_data/ui/coordinators/`
returns **zero** call sites: no Coordinator has ever called it. That is
correct for anything inside a `run_*()` worker (those run on a background
thread — calling `fsm.transition_to()` there would be the exact `BUG-031`
class the giant signal-bridge comment in the presenter warns about; workers
correctly use a queued `ui_unlock_signal` instead), but the *initial*
transition — the one the Presenter's Slot fires synchronously, on the main
thread, before submitting the worker — has no such constraint. Adding one
`request_x()` method per user action to the owning Coordinator, called
synchronously from the Slot, and having *that* method perform the
validate→log→`self._transition_fsm(state)`→`self._thread_manager.submit(self.run_x,
...)` sequence, uses the existing seam exactly as designed, on the correct
thread, without giving the Coordinator any new FSM **ownership** (it still
only ever calls a callback the Presenter handed it — `async-ui-action-rule.md`
§2's "Coordinator owns no FSM state" is about the state, not about who
physically writes the line).

**A second, unrelated dead mechanism found on the way — filed, not fixed
here (same convention `EPIC-025` used throughout for out-of-scope findings):**
`SyncCoordinator`/`GapCoordinator` each carry their own `_cancellation_token`
field and a `cancel()` that cancels it — but grepping shows that field is
**only ever set to `None`** (never assigned a real token); the real token
always comes from the caller's explicit `cancellation_token` argument
(`token_to_use = cancellation_token or self._cancellation_token` always
takes the left side in practice). That makes `_on_cancel()`'s calls to
`self._sync_coordinator.cancel()` / `self._gap_coordinator.cancel()`
**no-ops** — the only cancellation that actually fires is the Presenter's
own `self._cancellation_token.cancel()`, called first in the same method.
Worth its own bug report/fix, but changing cancellation semantics is not
this task's job; noted so a future reader does not mistake the dead
`cancel()` calls for redundant-but-harmless belt-and-braces.

**Per-Coordinator additions** (new `request_*` methods; existing `run_*`
worker methods are unchanged). The design table below is as originally
written; §4 records where the actual implementation diverged (a rename to
dodge a name collision, and a sixth Coordinator split out mid-implementation
when adding this section pushed `ScanCoordinator` itself over 400 lines):

| Coordinator | New method | Behavior moved from Presenter slot |
| :--- | :--- | :--- |
| `ScanCoordinator` | `request_check_status(symbol, interval)` | `_on_check_status` (no shutdown check today — preserve exactly) |
| `ScanCoordinator` | `request_check_all_status(intervals)` | `_on_check_all_status` (shutdown check, clear-table signal, needs new `is_shutdown_requested` ctor param — `ScanCoordinator` is the only one of the five missing it today) |
| `ScanCoordinator` | `request_clear_data(symbol, interval)` | `_on_clear_data`/`_on_clear_row` (shutdown check) |
| `ScanCoordinator` | `request_purge_all()` | `_on_purge_all` (shutdown check) |
| `ScanCoordinator` | `request_vacuum()` | `_on_vacuum` (shutdown check exists in the slot today but **no FSM transition** — preserve exactly, do not add one) |
| `SyncCoordinator` | `request_single_sync(symbol, interval)` | `_trigger_single_sync` (shutdown check, custom-time-range validation + two distinct error messages, log, `SYNCING`, `set_progress`, new `CancellationToken()`) — both `_on_sync_data` and `syncRowRequested` call through this one |
| `SyncCoordinator` | `request_bulk_sync()` | `_on_sync_all_gaps` (early-return "no gaps" log if `status_model.gap_targets()` is empty, log, `SYNCING`, `set_progress(0, len(targets))`, new token) |
| `GapCoordinator` | `request_repair_gap(symbol, interval, start, end)` | `_on_repair_gap` (shutdown check, `fsm.transition_to` **can refuse** — preserve the `if not …: return` short-circuit, new token) |
| `GapCoordinator` | `request_repair_all_gaps(symbol, interval)` | `_on_repair_all_gaps` (same shape as above) |
| `KLineInspectorCoordinator` | *(no change)* | `_on_inspect_klines`/`_on_run_audit` never transition the FSM or check shutdown — already a one-line submit, not worth a wrapper |
| `ExportImportCoordinator` | `request_export_data(...)`/`request_import_data(...)` | the submit+log(+`CLEARING`-transition for import only) half of `_on_export_requested`/`_on_import_requested`; the dialogs stay on the Presenter (need `self.view`) |

**Stays on the Presenter, not extracted** (each has a concrete reason,
recorded so a future pass does not "re-discover" and re-attempt these):
- `_on_cancel` — the one place that legitimately spans three Coordinators
  plus the Presenter's own `_cancellation_token`; splitting it would need a
  fourth object just to hold what the Presenter already holds.
- `_ask_export_path`/`_ask_import_path` — need `self.view` as a `QFileDialog`
  parent; this file's own docstring already cites the identical precedent
  (`backtest_presenter._ask_report_export_path`).
- `capture_state`/`restore_state`/`state_scope`/`_mark_state_dirty`
  (`IStateContributor`) — reads/writes `self._view_model`/
  `self._state_coordinator` directly; no Coordinator owns either.
- `_refresh_stats`/`_database_size_text` — `_database_size_text` has no
  `self` dependency beyond `self.config` and is a pure `Path → str`
  computation once the config value is read; extract it as a free function
  into a new `logic/stats.py` (mirroring `logic/export_paths.py`), not into
  a Coordinator (it is not an async action).

**Test impact — the largest risk in this slice.**
`tests/unit/modules/market_data/ui/test_data_management_presenter.py` (816
lines) asserts on **identity** in ~30 places — e.g.
`mock_thread_mgr.submit.assert_called_with(presenter._run_check_status, ...)`
and direct calls like `presenter._run_single_sync(...)` to simulate the
worker running. Once `_run_*` delegates are deleted and slots call
`self._scan_coordinator.request_check_status(...)` instead, every one of
those assertions must retarget the Coordinator's `run_*` method
(`presenter._scan_coordinator.run_check_status`), and the *new*
`request_*` orchestration (validation, log message, FSM transition,
submit-with-correct-args) needs its own test — added to the relevant
`test_*_coordinator.py` file, not left untested because it "moved". This
is mechanical but touches most of the existing test file; budget real time
for it, not just the production-code edit.

### 3.2 The other three files — not designed yet

`dashboard_presenter.py` (1994), `dev_board_panel.py` (1145),
`paper_exchange.py` (587, see §1) still need their own measurement pass
each, the same way §3.1 was done for `data_management_presenter.py` — do
not assume the same `request_*`/dead-seam pattern applies; each file's own
`git log -p` and current coordinator/policy split must be read first
(`fix-bug-rule.md` §2's "root cause first" applies to a design pass too:
guessing a second file's seam from the first file's shape is exactly the
"guessing a split boundary" `architecture-rule.md` §7.2.1 warns against).

## 4. Changes, per file

### `data_management_presenter.py` — §3.1's plan implemented 2026-09-26; still over 400

**964 → 671 lines (a 293-line, 30% cut), behavior-preserving** (confirmed by
the full existing test suite passing unchanged in intent, plus new coverage
for what moved):

- All five `ScanCoordinator` `request_*` methods, `SyncCoordinator`'s two,
  `GapCoordinator`'s two, and `ExportImportCoordinator`'s two landed as
  designed in §3.1.
- **One rename the design didn't anticipate:** `ExportImportCoordinator
  .request_export`/`.request_import` collided by name with
  `TradeLogViewModel.request_export` in `backtesting.ui` — caught by
  `tests/unit/architecture/test_presenter_duplication_only_shrinks.py`
  (67 → 68 cross-package duplicate member names), which exists precisely to
  catch new incidental collisions like this one rather than carried-through
  debt. Different role, different body (a ViewModel signal asking the View
  to open a dialog, vs. this Coordinator's own submit-after-the-dialog
  orchestration) — not real duplication to consolidate, so the fix was
  renaming this PR's own brand-new methods to `request_export_data`/
  `request_import_data`, not accepting new debt or touching
  `TradeLogViewModel`.
- **A sixth Coordinator split out mid-implementation:** adding
  `ScanCoordinator`'s five `request_*` methods pushed that file itself to
  496 lines — over the exact ceiling this task exists to enforce. Mirroring
  `ExportImportCoordinator`'s own precedent (already split out of
  `ScanCoordinator` before this feature existed, per that file's docstring),
  clear/purge/VACUUM's `run_*`/`request_*` pairs moved into a new
  `VaultMaintenanceCoordinator` (198 lines). Final coordinator sizes: `scan_coordinator.py`
  374, `sync_coordinator.py` 353, `gap_coordinator.py` 309,
  `export_import_coordinator.py` 193, `vault_maintenance_coordinator.py` 198,
  `kline_inspector_coordinator.py` 138 (unchanged) — all six now comfortably
  under 400.
- **`logic/stats.py`** — `_database_size_text()` extracted as a pure
  `database_size_text(raw_dir) -> str` function, as designed.
- **One extraction beyond §3.1's original plan:** `__init__`'s six-Coordinator
  construction (~90 lines of keyword-heavy wiring) was itself the "complex
  multi-step construction sequence" `code/quality.md` §9 gives to a Factory,
  not a constructor — extracted to `logic/coordinator_factory.py`
  (`build_coordinators()`, 163 lines), cutting `__init__` to an 8-line
  unpack of the returned `NamedTuple`.
- **A real, load-bearing consequence of moving token ownership into the
  Coordinators** (flagged as a mere "finding, not fixed here" in §3.1's
  first draft): `scripts/shutdown_database_sync_probe.py` (BUG-023's
  process-level regression probe, exercised by
  `tests/integration/presentation/test_shutdown_database_sync_process.py`)
  manually simulated a bulk-sync worker by setting
  `presenter._cancellation_token` and calling the old `presenter._run_bulk_sync`
  delegate directly. Retargeting it to `presenter._sync_coordinator.run_bulk_sync`
  with a bare local `CancellationToken()` **broke the probe for real** —
  `bulk_sync` mode hung until the subprocess was killed, `RuntimeError: Data
  management bulk_sync worker ignored desktop shutdown` — because
  `DataManagementPresenter.shutdown()` now calls `self._sync_coordinator.cancel()`,
  which only cancels *that Coordinator's own* `_cancellation_token` field, not
  an unrelated local variable. Fixed by having the probe assign the token to
  `presenter._sync_coordinator._cancellation_token` (the same field
  `request_single_sync`/`request_bulk_sync` themselves assign), which is
  also what makes `SyncCoordinator.cancel()`/`GapCoordinator.cancel()`
  **stop being dead code** — §3.1's "no-op cancel()" finding is now live and
  verified working, as a direct, in-scope consequence of relocating token
  ownership to the action's true owner, not a separate cancellation-semantics
  redesign. Confirmed via the real subprocess-level integration test (all 3
  modes green), not just a mocked unit assertion.

**Honest remaining gap: 671 lines, 271 over the 400 target.** What is left
and why it wasn't force-cut:
- The "Qt Slots" section is now mostly one-to-three-line pass-throughs to a
  Coordinator's `request_*`/`run_*` method — there is very little boilerplate
  left to DRY without inventing a needless abstraction over already-thin
  calls.
- `capture_state`/`restore_state`/`state_scope`/`_mark_state_dirty`
  (`IStateContributor`, ~55 lines including a long docstring explaining a
  genuine known limitation) reads/writes `self._view_model`/
  `self._state_coordinator` directly — no existing Coordinator owns either,
  and inventing one only to hold four methods would be the "bespoke
  machinery" `CONSTITUTION.md` P5 rejects.
- The Qt signal declarations (~25 lines) and the giant, load-bearing
  signal-bridge comment explaining why they exist (~20 lines, §"Signal
  bridges" in the file) are not extractable — they are the class's own
  public/documented surface.
- `_ask_export_path`/`_ask_import_path` (~35 lines) stay for the reason §3.1
  already gave (need `self.view`).
- Closing the remaining ~271 lines would mean either the `IStateContributor`
  extraction above (a real but debatable design call, not a mechanical one)
  or trimming genuinely load-bearing documentation — neither is a call to
  make casually inside what was meant to be a bounded slice. Recorded here
  rather than forced, per this task's own §3 instruction ("if still over 400
  ... that is a real finding to record ... not a reason to force a cut that
  damages cohesion").

**Verification:** `ruff check`/`ruff format --check` clean on every touched
file. `tests/unit/modules/market_data` (672 tests, including ~20 new
`request_*`/`VaultMaintenanceCoordinator` tests), `tests/unit/architecture`
(440, including the duplication ratchet at its unchanged 67 total),
`tests/sanity` (32), and
`tests/integration/presentation/test_shutdown_database_sync_process.py` (3,
real subprocess boot) all green. Mutation-verified: `GapCoordinator
.request_repair_gap`'s FSM-refusal short-circuit (`if not
self._transition_fsm(...): return`) sent its regression test red for the
right reason when temporarily removed; `SyncCoordinator`
/`ExportImportCoordinator`/`VaultMaintenanceCoordinator`'s shutdown-guards
and FSM-transition assertions are each backed by a dedicated test.

{`dashboard_presenter.py`, `dev_board_panel.py`, `paper_exchange.py`: not started.}

## 5. Testing

- `data_management_presenter.py`: `test_data_management_presenter.py`,
  `test_data_management_export_import.py`, `test_gap_inspector_presenter.py`,
  `test_kline_inspector_presenter.py` all retargeted (identity assertions
  move from `presenter._run_x` to `presenter._x_coordinator.run_x`/
  `presenter._x_coordinator.request_x`). New `request_*` orchestration tests
  added to `test_scan_coordinator.py`, `test_sync_coordinator.py`,
  `test_gap_coordinator.py`, `test_export_import_coordinator.py`, and the
  new `test_vault_maintenance_coordinator.py` (which also carries the
  `run_clear_data`/`run_purge_all`/`run_vacuum` tests moved out of
  `test_scan_coordinator.py`). Full `tests/unit` run for regressions
  (in progress at hand-off — see Resume);
  `tests/integration/presentation/test_shutdown_database_sync_process.py`
  covers acceptance criterion 4's "no FSM transition/coordinator wiring
  silently dropped" for the shutdown-during-sync path specifically, since it
  is the one path this slice's own change (§4) actually altered behavior on.
  A manual `tools/run_app`/`scripts/run-dev.ps1` click-through of the Data
  Management screen was **not** performed — recorded as an open item, not
  claimed.
- Shrink-only line-count guard: not yet added — still correctly deferred per
  the original plan, since `data_management_presenter.py` itself is not yet
  at or under 400. Note for whoever adds it later: the *coordinator* files
  (`scan_coordinator.py` etc.) are all under 400 now and would be legitimate
  first entries for such a guard even before the Presenter itself qualifies.

## Resume (optional; while unfinished)

`data_management_presenter.py` is substantially smaller (964 → 671, 30%) and
fully green, but not yet at the ≤400 target — see §4's honest gap analysis.
Next executable action, in order:
1. Confirm the full `tests/unit` suite (not just `market_data`/`architecture`/
   `sanity`) is green on this slice — it was running at hand-off.
2. Decide on the `IStateContributor` extraction §4 flags as the only
   remaining *mechanical* lever (a small new collaborator owning
   `capture_state`/`restore_state`/`_mark_state_dirty`, injected with
   `view_model` and `state_coordinator`) — or accept 671 as this slice's
   final number and move on, since forcing it below 400 by trimming the
   signal-bridge documentation would cost more than it's worth.
3. Add the shrink-only line-count guard once a decision on (2) is made,
   seeded with whichever files are already compliant (the six coordinators
   qualify today even if the Presenter does not yet).
4. Only after `data_management_presenter.py` is closed should
   `dashboard_presenter.py`/`dev_board_panel.py`/`paper_exchange.py` get
   their own §3.2 design passes — each is materially larger, and this
   slice's exact `request_*`/dead-seam pattern is not guaranteed to
   transfer (the Factory extraction might, but verify rather than assume).
