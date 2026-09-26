# BOT-144 — Four files split back under the 400-line ceiling

**Status:** 🟡 In progress — `data_management_presenter.py` slice implemented and merged 2026-09-26 (`PR #270`): 964 → 671 lines (30% cut), still over the 400-line target; the `IStateContributor` extraction was decided against, not deferred (§4). The shrink-only line-count guard (acceptance criterion 5) is also done (`PR #271`, merged). `paper_exchange.py` is now done too — 596 → 372 lines, ≤400 at last (§4). `dashboard_presenter.py` has a measured design (§3.2) but no code changed yet; `dev_board_panel.py` not started.
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
- [x] `paper_exchange.py` is ≤400 lines, achieved by extracting its remaining position entry/exit lifecycle (`_open()`/`_close()`/`_close_one_position()`/`_close_partial_position()`/`_apply_partial_take_profits()`) into a domain policy under `domain/policies/`, mirroring the extraction `PR #266` already did for `StopManagementPolicy`. **Done 2026-09-26** — see §4.
- [ ] Every existing test for these three files (and their coordinators/view models) still passes unchanged in behavior — a test may need its constructor call updated for a new collaborator, but must not need its assertions weakened.
- [ ] No FSM transition, signal connection, or coordinator wiring present before the split is silently dropped — verified by running the full `tests/unit` suite plus a manual `tools/run_app` (or `scripts/run-dev.ps1`, whichever this repo's `run` skill uses) smoke pass on the Dev Board and Data Management screens.
- [x] A machine guard is added (or an existing one extended) so a file already over 400 lines cannot grow further without the gate failing — closing the gap the independent review noted ("no guard test currently catches this"). A shrink-only ratchet, mirroring `test_app_styling_only_shrinks.py`'s own pattern, is the vetted precedent to apply before inventing a new mechanism. **Done 2026-09-26** — see §4.

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

### 3.2 `dashboard_presenter.py` (1994 → target ≤400) — measured 2026-09-26, design in progress

Measured, not guessed, before designing anything (`fix-bug-rule.md` §2):
section-by-section outline via the file's own `# ===` banners, then read the
two largest candidates in full.

**Two real candidates found, each with its own reason:**

1. **`__init__` (519–909, ~390 lines)** — the same "complex multi-step
   construction sequence" `code/quality.md` §9 gives to a Factory that
   `coordinator_factory.py` already extracted for `data_management_presenter.py`.
   **Does not transfer as a pure copy of that precedent, though** — verified
   by reading it, not assumed: it interleaves FSM transition wiring that
   must run in a specific order, several nested closures
   (`_get_cancellation_token`/`_reset_cancellation_token`/
   `_get_active_interval`/etc.) capturing `self` and reading/writing state
   defined earlier in the *same* constructor, and explicit sequencing
   comments ("restore state only after X exists", "constructed last: it
   immediately calls `_on_start_stream()`"). A Factory extraction is still
   the right target, but it has to take these closures and orderings as
   parameters/return values rather than mechanically relocating lines — more
   design work than `data_management_presenter.py`'s equivalent, not a
   same-shape port.

2. **Enable/Disable toggle + Emergency Stop + Manual order + Per-order
   cancel (1235–1627, ~392 lines)** — shape-matches the Coordinator pattern
   this same file already uses for `SymbolOptionsCoordinator`/
   `LiveOrderBookCoordinator`/`StrategyArmingCoordinator`/
   `IndicatorCoordinator` (`_on_x_requested` → validate/track → submit to
   `IThreadManager` → `_run_x` worker) almost exactly, and is currently
   **not** using it — the same "seam pattern established elsewhere in the
   file, not applied consistently" finding §3.1 made for
   `data_management_presenter.py`'s dead `transition_fsm` seam.
   **A real reason found here, not assumed to transfer — corrected
   2026-09-26 after PR #271's independent review reproduced the actual
   mechanism against this repo's pinned `PySide6==6.11.1` and disproved this
   entry's first-draft claim:** an earlier version of this paragraph argued
   the five `_on_x_completed` `@Slot(tuple)` handlers had to stay
   Presenter-owned because Qt's queued-connection marshaling depends on the
   connected slot being a bound method of a `QObject`. That is false —
   `AutoConnection`'s queuing decision is governed by the **signal owner's**
   thread affinity (`DashboardPresenter`, always main-thread) versus the
   emitting thread, not by whether the connected callable's own object is a
   `QObject`; a plain Coordinator's method is marshaled exactly as safely,
   confirmed both by a live repro and by this codebase's own existing
   precedent (`SyncCoordinator`, a plain non-`QObject`, already reaches a
   Presenter-owned signal's `.emit()` from a background thread without
   incident). **The real, still-standing reason the five `_on_x_completed`
   handlers cannot move is `async-ui-action-rule.md` §2: a Coordinator owns
   no action-id/FSM bookkeeping — the owning Presenter keeps its own
   `ActionOwnershipTracker`, and `_on_enable_trading_completed` (etc.) calls
   `self._toggle_tracker.finish_action(...)` directly.** The practical
   conclusion is unchanged — only the `_run_x` workers and the four
   `_on_x_requested` synchronous request-orchestration methods move into a
   Coordinator; the five `_on_x_completed` handlers (~140 of the ~392 lines)
   stay Presenter-owned — but for this reason, not a Qt-threading constraint
   that does not exist. A partial win (~250 lines), not the ~392 a naive
   port would claim.

**Not yet designed** (need their own read before any claim about them):
`BasePresenter` contract implementations / engine event bridge (1050–1235),
FSM Hooks / UI Helpers (1664–1721), custom indicator script orchestration
(1723–1748, likely stays — `IndicatorCoordinator` already owns the async
half), Qt Slots for chart/stream actions and Background Signal Slots
(1748–1899, likely mostly delegates to `StreamLifecycleController`/
`HistoryPaginationController` already — needs confirming, not assuming),
Engine Event Bridge / tick handling (1899–1991).

**Sizing reality check:** even both candidates above together
(~390 + ~250 = ~640 lines) would land this file around **~1350 lines** —
still far over 400. Confirms this task's own `Complexity: L` framing ("no
single mechanical transform covers all three") rather than a quick win;
expect this file alone to need more than one slice. Implementation not yet
started — the next executable action is the Coordinator extraction (item 2
above), since it is the better-understood, lower-conceptual-risk half; the
`__init__` Factory (item 1) should follow once the Coordinator's
construction lines have already moved once, reducing what the Factory has
to carry.

### 3.3 `paper_exchange.py` (596 → 372) — designed and implemented 2026-09-26

§1 had already named the target precisely: the entry/exit/trade-recording
lifecycle (`_open()`/`_close_one_position()`/`_close_partial_position()`/
`_apply_partial_take_profits()`) was the one extraction left after `PR #266`'s
`StopManagementPolicy` split, deliberately deferred rather than attempted
inside a feature PR. No further design pass was needed beyond confirming the
shape, which differs from `StopManagementPolicy` in one real way: that policy
never touches `self._balance`/`self._trades` (it only adjusts pre-fill risk
state on the `OpenPosition` objects themselves), while these four methods are
exactly the "books" mutations — cash and the trade log — the class's own
docstring names as its core responsibility. A stateless policy that also
needs to update a caller's `balance` cannot mutate a `float` in place, so the
new `PositionLifecyclePolicy` follows the same "return the new state, let the
caller apply it" idiom `paper_exchange.py`'s own `check_intrabar_stops()`
already uses for `FillPricing.evaluate_liquidations()`/
`evaluate_intrabar_stops()` — extended here rather than invented, per
`architecture-rule.md` §7.2.1's "mirror proven structures" instruction.
`PaperExchange` keeps owning `self._balance`/`self._positions`/`self._trades`
(the ledger) and applies the deltas/replacements the policy returns; it never
hands the ledger itself to the policy. Individual `OpenPosition` field
mutation (e.g. `close_partial_position()`'s in-place quantity reduction)
stays exactly as before — the same pattern `StopManagementPolicy` already
uses on the same domain entity, not new.

`_close()`'s own ~30 lines of orchestration (filter positions by side, loop
calling the policy's `close_one_position()`, filter the remainder) stayed on
`PaperExchange` rather than moving into the policy too — extracting it would
have pushed `positions` in as a fifth parameter alongside `side`/`price`/
`time`/`exit_reason`, over `code/quality.md` §7's 4-argument limit, for a
thin loop that isn't itself complex enough to be worth the parameter-object
indirection that would otherwise be needed to dodge that limit.

**Result:** `paper_exchange.py` 596 → 372 lines (≤400, done); new
`domain/policies/position_lifecycle_policy.py` at 384 lines (also ≤400 — no
new violator). No test file needed retargeting: `test_paper_exchange.py`
(1814 lines, 95 tests) exercises `PaperExchange` only through its public API
(`fill`/`force_close`/`check_intrabar_stops`/properties), never the private
methods that moved — confirmed by grep before starting, not assumed. All 95
tests pass unchanged, plus the full `tests/unit/modules/backtesting` suite
(972 tests) and `tests/unit/architecture` (445, including the god-files guard
once its baseline entry for this file was removed — see below). `ruff`/`mypy`
clean.

**Guard bookkeeping:** `paper_exchange.py`'s entry in `baseline_god_files.json`
removed in the same commit (596 → 372 is now under the ceiling), per
`test_god_files_only_shrink.py`'s own "lower the baseline in the same commit"
rule — confirmed the guard actually catches a stale entry first (it failed
before the removal, naming this exact file).

### 3.4 `dev_board_panel.py` (1145) — measured 2026-09-26, none of the other three shapes transfer

Measured before designing (`fix-bug-rule.md` §2): this is a View-layer
widget-builder (`DevBoardPanel(QObject)`, no Presenter, no async actions),
not a Presenter or a domain policy — `async-ui-action-rule.md` §2's
Coordinator pattern and `paper_exchange.py`'s return-new-state policy shape
both have no subject here (nothing async, no ledger). The file's own class
docstring states a real, load-bearing constraint that has to survive any
split: **"Every private attribute stays where it was, because that is what
the tests and the Presenter key off"** — confirmed by grep, not assumed:
`test_dev_board_panel.py` reads `panel._btn_start`/`_txt_start_date`/
`_script_checkboxes`/`_progress_banner`/etc. directly, and `DashboardView`
reads the four public properties (`header_actions`/`status_tiles`/
`dock_panels`/`manual_order_card`) built from those same private attributes.

**Why the obvious "extract each `_build_x_card` into a free function" port
does not work here** — checked by reading every `_build_*` method in full,
not assumed from their names: unlike `coordinator_factory.py`'s six
`Coordinator(...)` constructor calls (independent, side-effect-free objects),
each `_build_x_card()` here interleaves widget construction with (a) signal
connections that target `self`'s *other* methods (`self._btn_arm_strategy
.clicked.connect(self._view_model.strategy.requestArm)` is fine to extract,
but `self._btn_strategy_params.clicked.connect(self._open_strategy_params_dialog)`
and lambdas like `lambda: self._on_manual_order_clicked(ManualOrderDirection.LONG)`
close over `self`), and (b) calls to `self`'s own `_sync_*` methods to set
correct initial state before the method returns (e.g. `_build_strategy_card()`
ends by calling `self._sync_strategy_options()`/`_sync_strategy_selection()`/
`_sync_armed_summary()`). A free function taking every one of these as a
separate callback parameter would need 8–12 parameters per card — the
"closed-design tell" `architecture-rule.md` §7.2.1 names directly, not a
seam to build.

**The real target: componentize each card into its own `QWidget` subclass**
(`SystemControlsCard`, `StrategyCard`, `ManualOrderCard`, `SessionCard`,
`LastSignalCard`, each under a new `dashboard/dev_board_widgets/` package),
mirroring how `WsStatusPill` (already imported here) and this repo's other
extracted "Card" widgets (`EPIC-007`'s card standardization,
`BOT-124`'s shared `DataTable`) already work: the widget owns its own
buttons/fields, connects its own signals to the `view_model` directly where
the wiring is static, and exposes a small, real constructor
(`view_model: DashboardQmlViewModel`) plus whatever narrow callables it
needs for the handful of connections that aren't to the view_model itself
(e.g. `ManualOrderCard` needs `on_order_clicked: Callable[[ManualOrderDirection],
None]` for its two buttons, not all of `DevBoardPanel`). Each card keeps its
own `_sync_*` methods internally, called from its own `__init__` and from
whichever `view_model` signal currently drives them — this is a real move of
behavior, not just widget construction, unlike the "layout only" first idea.

**Preserving the private-attribute contract**: `DevBoardPanel.__init__`
constructs each card (`self._strategy_card_widget = StrategyCard(view_model)`)
and re-exposes every attribute a test currently reads directly as a
pass-through property or a direct reassignment (`self._btn_start =
self._system_controls_card_widget.btn_start`) — mechanical, but it is the
one part of this split that must be checked field-by-field against the
grepped list below, not sampled, since a single missed name is a silent
regression only a targeted regression test (or an attentive human) would
catch, and the file's own docstring is explicit that these are load-bearing.

**Full grepped list of attributes `test_dev_board_panel.py` and
`DashboardView`/`DashboardPresenter` read directly** (the exact contract
any split must preserve): `_btn_load_history`, `_btn_pick_range`,
`_btn_reload`, `_btn_start`, `_btn_stop`, `_btn_symbol`, `_log_panel`,
`_price_ticker_label`, `_progress_banner`, `_script_checkboxes`,
`_symbol_picker`, `_symbol_preferences`, `_time_range_dialog`,
`_txt_end_date`, `_txt_start_date`, `_ws_status_pill` (test file), plus the
four public properties (View).

**Sizing estimate, not yet implemented**: the five `_build_*_card` methods
plus their paired `_sync_*`/`_on_*` methods (the content that would move
into the new card widgets) account for roughly 550–650 of this file's 1145
lines; `_build_header_widgets`/`_build_progress_banner`/`_build_indicators`
(the header, and the indicators checklist which is driven by a dynamic,
per-script list rather than a fixed card) are smaller and more entangled
with `DevBoardPanel`'s own script-catalog/symbol-preferences state, and were
not sized in this pass — a second, later reason to expect this file to need
more than one slice, the same way `dashboard_presenter.py` does.

**Not implemented in this PR.** This is a materially larger and riskier
change than the other two files' extractions (financially-adjacent live
trading controls, with a documented cross-file private-attribute contract
to preserve exactly), and rushing it inside the same batch as two already-
verified extractions would risk the whole PR's reviewability. Recorded here
as a real, checked design rather than left as a guess, so the next session
does not have to re-derive it.

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

### Line-count guard — added 2026-09-26 (acceptance criterion 5)

`tools/measure_god_files.py` scans `src/**/*.py` and returns every file over
`architecture-rule.md` §5.4's 400-line ceiling. `baseline_god_files.json`
freezes today's 29 violators (measured the same day PR #270 merged — the
count moved 964 → 671 for `data_management_presenter.py` in that same PR, so
the baseline was taken *after* it, not before).
`tests/unit/architecture/test_god_files_only_shrink.py` is the ratchet:

- a file already in the baseline may shrink freely but never grow past its
  recorded count (mirrors `test_app_styling_only_shrinks.py`);
- a file crossing 400 lines for the **first time** fails outright — deliberately
  **not** offered a baseline-edit escape hatch the way the styling census
  allows, since this rule's remedy is "split it", not "grandfather it in";
- a baseline entry that drops out of the measured set (shrunk under 400,
  moved, or deleted) fails too, forcing the baseline down in the same commit.

Scope is `src/` only (`tests/`/`tools/` also exceed 400 lines in many places —
`architecture-rule.md` §5.4 names them too, but freezing that debt as well is
a separate, larger undertaking than this task asked for). Registered in
`scanned_roots_registry.py` and `test_guard_scans_its_registered_root.py`'s
`_UNRESOLVABLE_GUARDS` (scans via an imported function, not a literal
`.rglob()` in its own body — same shape as `test_module_boundaries.py`'s
neighbors). Mutation-verified all three directions (a file grown past its
baseline, a new violator with no baseline entry, a stale baseline entry no
longer over the ceiling) — each failed for the stated reason, then reverted.

### IStateContributor extraction — decided 2026-09-26, not done

Resume step 2 asked to decide, not just defer again. Decision: **do not
extract it.** The four methods (`capture_state`/`restore_state`/
`state_scope`/`_mark_state_dirty`) have exactly one real collaborator each
(`self._view_model`, `self._state_coordinator`) and no existing Coordinator
owns either — inventing a class to hold four methods purely to cross a line
count would be the "bespoke machinery" `CONSTITUTION.md` P5 rejects, not a
seam any other consumer needs (`architecture-rule.md` §7.2.1: a seam is built
for a plausible *second* case, and there isn't one here). `671` lines stands
as this slice's final number; the line-count guard above now holds that
ground so it cannot silently grow back toward 964.

### `paper_exchange.py`: done — see §3.3. `dashboard_presenter.py` designed (§3.2), not implemented. `dev_board_panel.py`: not started.

Now unblocked by the guard above (each file's current count is the frozen
baseline, so no further work here makes them worse by accident). `dev_board_panel.py`
still needs its own measurement-and-design pass before touching code — do not
assume any of the three shapes found so far transfers.

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

`data_management_presenter.py` is substantially smaller (964 → 671, 30%),
merged, and fully green. Steps 1–3 below are done; only step 4 remains open.

1. ~~Confirm the full `tests/unit` suite is green on this slice~~ — done
   (5451 passed), confirmed before `PR #270` merged.
2. ~~Decide on the `IStateContributor` extraction~~ — decided against (§4):
   671 stands as this slice's final number.
3. ~~Add the shrink-only line-count guard~~ — done (§4), scoped to `src/`,
   seeded with all 29 current violators including this file's own 671.
4. `dashboard_presenter.py`'s §3.2 design pass is done (measured, two
   candidates found, one real mechanism difference from
   `data_management_presenter.py` recorded: `_on_x_completed` `@Slot`
   handlers cannot move off the Presenter, only `_run_x`/`_on_x_requested`
   can — see §3.2). **Next executable action:** implement candidate 2 (a new
   Coordinator for Enable/Disable toggle + Emergency Stop + Manual order +
   Per-order cancel, ~250 lines moved, `_on_x_completed` staying Presenter-side)
   — smaller blast radius and better-understood than candidate 1's `__init__`
   Factory, which should follow once this lands. Budget real time for
   retargeting `test_dashboard_presenter.py` (2903 lines) the same way
   `test_data_management_presenter.py` needed it. `dev_board_panel.py` (1145)
   and `paper_exchange.py` (596, target for a `domain/policies/` extraction
   mirroring `StopManagementPolicy`) still need their own §3.2 passes after.
