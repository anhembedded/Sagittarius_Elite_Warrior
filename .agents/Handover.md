# Handover — start here

This is the "first five minutes" file for an AI new to this repository. It
tells you what the project is, where the real rules live, how to verify a
change, and which mistakes have already bitten a previous AI session so you
don't repeat them. It does not duplicate the rules themselves — it points
you at the file that owns each one, so there's a single source of truth.

## Latest session handover (2026-08-20) — Epic `BOT-109` (Golden Reference Strategy): `BOT-041`/`BOT-050`/`BOT-110` all closed, one real provisional-state bug found and fixed

**Epic `BOT-109`** (port TradingView's "EMA Trend Confirm + Pullback + TP%"
Pine Script v6 strategy 1:1 as the app's golden reference) is now 3/4 steps
done — only `BOT-111` (visual polish: draw the 2 EMAs, Buy/Sell/Short/Cover
markers, E2E verification via `.\scripts\ci-local.ps1 -Full`) is left.

**`BOT-041`** (SL/TP + risk-based position sizing) and **`BOT-050`**
(short-selling) shipped first, both fully additive to `PaperExchange` — 100%
of the pre-existing test suite passed unmodified at every stage (19→45
tests). `BOT-050`'s own design question ("when Long and a SELL arrives,
close-only or reverse-into-Short?") was put to the user directly; the
answer — *"không phải đây là chuyện của script stategy sao ta?"* (isn't this
the strategy script's own business?) — settled it: `SignalAction` gained
distinct `SHORT`/`COVER` members instead of overloading `BUY`/`SELL` for 4
meanings, so a strategy always states its own intent and `PaperExchange`
never infers it. Two mutation tests were "false passes" during `BOT-050`
(a guard-disabling mutation still passed because default `pyramiding=1` and
default 100%-equity sizing independently blocked the same action) — both
caught only by mutating, not by the test looking reasonable on paper; see
`Tasks/completed/BOT-050_short_selling_support.md` for the full mutation
log if you're about to trust a guard test at face value.

**`BOT-110`** (`EmaTrendPullbackStrategy`, the actual strategy class) is the
one with a real finding worth reading before touching `Series`-based
accumulator state anywhere in this codebase. Its own architecture question
(strategy needs to know current position side to emit `SELL` vs `COVER` on
an identical touch-exit condition, but `StrategyContext` was fully
position-blind by design) was resolved additively:
`StrategyContext.current_position_side: PositionSide | None = None`, filled
in by both backtest handlers from a new `PaperExchange.current_side`
property before each `on_tick`/`on_forming_bar_tick` call.

**The real bug**: `_update_trend_confirmation()` read `series[0]` as "the
previous bar's committed state" before computing and `track()`-ing the new
one. That's only correct on a bar's *first* tick. On the 2nd+
`on_forming_bar_tick()` call for the same still-forming bar, `[0]` already
holds *this* bar's own not-yet-committed provisional guess from the prior
tick (poked by this same method) — so the accumulator fed its own tentative
output back into itself as if it were settled history, and could advance
`confirmed_trend` several times within one bar instead of exactly once on
real close. This is precisely the bug class `BOT-042`'s provisional/commit
machinery exists to prevent, silently reintroduced by an accumulator
reading its own live-updating series as its own "previous" input — going
through `track()` does **not** protect against this pattern by itself.
Fixed with a new `Series.committed(offset)` method
(`src/domain/scripting/series.py`) that always reads the last bar that
actually closed, ignoring any pending provisional — `_update_trend_confirmation()`
and `_entry_confirmation()` both switched from `series[0]` to
`series.committed(0)`. **If you write a new strategy with any counter/state
that reads its own history to compute its own next value (not just a
cross/comparison read), use `.committed()`, not `[0]`, or it will silently
break under `on_forming_bar_tick()` while looking correct under `on_tick()`
alone — exactly the trap that hid this bug from `BOT-076`'s Realtime engine
for as long as it did.**

This was found because the first version of the tick-safety regression
test was itself a false pass: it drove `on_forming_bar_tick()` 20 times
with a *static, unchanging* candle *after* the trend was already
confirmed — every tick recomputed the identical answer regardless of which
read (`[0]` vs `.committed(0)`) was used, so it couldn't distinguish
correct from buggy. Rewritten to use a bar that is deliberately one bar
short of `tick_confirm` with a pullback-shaped candle, so a premature
confirmation surfaces as an observable, wrong `BUY` signal rather than
being absorbed by an already-saturated `confirmed_trend`. Mutation-verified
both ways (reverting `.committed(0)` back to `[0]` makes the rewritten test
fail with the exact predicted false `BUY`).

**Git note for whoever picks this up next**: this repo's working directory
was shared with a concurrent AI session during this work — the checked-out
branch on `master-warrior` changed underneath without action taken here at
least twice (another session's commits/pushes), each time resolved via
`git merge-base --is-ancestor` verification before any fast-forward, never
by force. If you see the branch move on its own, don't assume corruption —
check ancestry first. Full suite (`--ignore=tests/integration/presentation/ui`):
1539 passed, `ruff` clean. Local `master-warrior` is 1 commit ahead of
`origin/master-warrior`, not pushed this session.

## Prior session handover (2026-08-19, later same day) — `BOT-076` fully closed, Symbol Picker (`BOT-102`) shipped, a real Dirty-Tracking bug found and fixed

**`BOT-076` (Realtime Backtest engine) is now fully closed, moved to
`Tasks/completed/`.** §3.3 (UI wiring) is done: `OrderExecutionModal.qml`
unlocks the tick-based execution mode, `BackTestPresenter` branches between
`RunRealtimeBacktestCommand`/`RunStaticBacktestCommand` based on
`BacktestExecutionMode`, results are labeled "Realtime (tick ...)" vs
"Static (theo nến đóng)" so they never look identical with different
meanings, and `TickModeRequiresBoundedRangeRule` rejects tick mode combined
with "Toàn bộ lịch sử" (an unbounded `start_time` made the coverage query's
window-function scan grow forever while the live-trailing cutoff kept
moving — a real session got stuck in an infinite "Đồng bộ dữ liệu ngay"
retry loop because of this before the rule existed). §3.5 (play/pause/replay
speed) was explicitly dropped by user decision — asked directly, answer was
"drop it, close out BOT-076," don't resurrect it as a gap.

**A real bug was found and fixed while adding this: `BOT-076`'s tick loop is
CPU-bound Python with no yield points, and even though it genuinely already
runs on a background `ThreadPoolExecutor` thread (verified: `IThreadManager`
is a real `concurrent.futures.ThreadPoolExecutor`, not a fake), sustained
GIL contention from that loop still makes the UI thread sluggish — the user
reported this as "chạy trên UI thread kìa" and the instinct to believe them
literally would have been wrong. Filed as
[`BOT-103`](../Tasks/backlog/BOT-103_realtime_backtest_gil_contention.md)
with 3 remediation options (periodic `time.sleep(0)`, `ProcessPoolExecutor`,
reduce per-tick indicator cost) — **not started**, no direction chosen yet.

**`BOT-102` (Backtest Symbol Picker) shipped.** Backtest previously had no
way to change the trading symbol from the UI — `self._symbol` was set once
in `BackTestPresenter.__init__` from config and never written again. User
chose a real Binance exchange-info source over a static list (bigger
scope, no existing infra reused — `BOT-095E1`'s market-metadata cache is a
different concern, per-symbol filters, not a symbol *listing* call — this
repo had genuinely never called Binance exchange-info before). New:
`IExchangeClient.get_available_symbols()` + `ListAvailableSymbolsQuery`,
`SymbolPickerModal.qml` (grid + client-side search, since Binance returns
1300+ tradeable symbols — the other pickers, Strategy/Timeframe, never
needed search). **Architectural rule preserved on purpose:** `self._symbol`
on the Presenter stays the single source of truth every command/query
reads; `BackTestViewModel.selectedSymbol` is only ever a write channel from
the modal, never read from a background thread — matches this repo's
existing "background workers never touch the ViewModel directly" rule.
Verified with a real-window probe script (real app boot via `create_app()`,
a genuine `QTest.mouseClick` on the real button, a real network call that
fetched 1361 live symbols from Binance, search-filter and full
selection-round-trip checks, 2 screenshots) — not just automated tests.

**Found independently while verifying `BOT-102`, via a user-supplied
dev-mode log: `_build_run_config()` built `BacktestRunConfig(...)` without
`symbol=self._symbol`, silently falling back to the dataclass's own
`"ETHUSDT"` default.** This is a pre-existing bug (nothing to do with the
picker), invisible to every prior test because the test fixture's own
default symbol happens to be `"ETHUSDT"` too — coincidence masked it. Real
impact: `lastRunSummary` showed the wrong symbol after every completed run,
and Dirty Tracking's `compute_diff_summary()` would report a fake "Symbol
(... → ...)" change on the very next toolbar edit for anyone whose
configured default symbol isn't ETHUSDT, even with zero real changes. Fixed
(one line), with a regression test that deliberately configures a
*different* symbol so the dataclass default can't coincidentally mask it
again — see `test_build_run_config_carries_the_presenters_actual_symbol_not_the_dataclass_default`
in `tests/unit/presentation/ui/screens/test_backtest_presenter.py`. **If you
add a third `BacktestRunConfig(...)` construction site anywhere, grep for
this test's name first and make sure it would still catch a missing
`symbol=`.**

**Also this session:** `BUG-009` (chart drag inside the grid moved the
whole graph) is fixed and verified — see its own file for the final root
cause, `Tasks/bug_report/BUG-009_backtest_cached_frame_preview_widget_shift.md`.
The engine-side crash-on-every-launch
(`ModuleNotFoundError: sagittarius_engine.infrastructure.logging.dev_verbosity`)
is fixed — a prior session's submodule commit referenced a module that was
never actually created/committed in the `Sagittarius-Engine` engine repo;
rebuilt end-to-end with `TRACE`/`critical` log level support. A Cancel
button for an in-progress data sync now exists (FSM's `CANCELLING` state
extended to be reachable from `SYNCING`, plus a real race-condition fix:
`_on_sync_succeeded_for_action`/`_on_sync_failed_for_action` lacked the same
cancelling-guard the `BACKTEST`-kind handlers already had). While closing
out `BOT-076`, `BOT-024` (Backtest Replay UI — play/pause/speed) was found
sitting in the backlog as the *same* feature `BOT-076` §3.5 had just been
told to drop, under a different task ID from before the two were linked —
cancelled it too (`Tasks/cancelled/BOT-024_backtest_screen_dynamic_ui.md`),
confirmed with the user first.

## Prior session handover (2026-08-19, earlier same day) — Epic `BOT-042` closed, `BOT-076` core engine built, `BOT-075` spike done

**Big picture: the Realtime Backtest epic (`BOT-073`) is no longer blocked.**
Both of its hard prerequisites finished this session —
[`BOT-075`](../Tasks/backlog/BOT-075_tick_data_feasibility_spike.md) (tick
data feasibility) and [`BOT-042`](../Tasks/backlog/BOT-042_tick_level_strategy_engine_support.md)
(provisional/commit contract) — and
[`BOT-076`](../Tasks/completed/BOT-076_realtime_backtest_engine.md) (the
engine itself) now has a real, tested core (§3.1 use case + §3.2 replay
loop). **Read `BOT-076`'s own file before touching it again** — its top note
says exactly what's done vs. open, don't re-derive.

**`BOT-075` (tick feasibility spike) — done, real numbers, no more guessing.**
Synced 7 real days of `BTCUSDT` at `1s` via Binance public REST: 604,801
rows, 120.12 MiB `.db` (checkpoint the WAL before trusting `os.path.getsize()`
— right after `save_klines()` it lies), a `get_klines()` query over that
range takes 6.32s, and a real `RunStaticBacktestCommandHandler` pass over
all of it takes 10.98s. **Conclusion: feasible, but not synchronous-UI-safe**
(~17s total) — must run in the background with the existing
`CancellationToken` machinery (already built for `BOT-034`/`BOT-095C`, don't
build a new one), and should let the user pick 1s/5s/15s resolution rather
than hardcoding 1s. Data source decided: `1s kline`, not `aggTrades` (half
the request weight, existing pipeline needs zero changes, `aggTrades` has no
client adapter at all). Full report:
[`Tasks/reports/tick_data_feasibility.md`](../Tasks/reports/tick_data_feasibility.md).

**`BOT-042` (provisional vs. commit) — done, all 4 sub-tasks (A design,
B indicators, C `Series`, D `StrategyEngine`), now in `Tasks/completed/`.**
The core mechanism: `IIndicator` gained `peek_provisional(value)` alongside
`update(value)` — same formula, but reads committed state and returns a
result **without writing it back**, so it's safe to call any number of
times per bar. `EMA`/`RSI` do this by using a local variable instead of
`self._ema =`; `WMA` has no closed-form recurrence so it builds a temporary
window from the deque without appending to it (O(period), not O(1), the one
exception); `MACD` just calls `peek_provisional()` on its 3 sub-`EMA`s in
the same order `update()` does. `Series` gained a `poke_provisional()` and a
`_NoProvisional` sentinel (distinct from `None`, which is itself a valid
provisional reading) — while a provisional value is set, `Series[0]` reads
it and every other offset shifts by one, so `crossed_above`/`crossed_below`
needed **zero changes** and are automatically correct, including the
cold-start case (no committed history at all yet — already handled safely
by the pre-existing `__getitem__` bounds check, just needed an explicit test).

**Real gap the task doc didn't anticipate, found while wiring `StrategyEngine`:**
`Series.push()` turns out to be called **directly inside each concrete
strategy's `decide()`** (`EmaCrossoverStrategy`, `MultiEmaTrendFollowerStrategy`),
not inside `StrategyEngine` — so adding `StrategyEngine.on_forming_bar_tick()`
alone would compute correct provisional indicator readings but still
`push()` them straight into `Series`, corrupting committed cross-detection
history. Fixed with `BaseStrategy.track(series, value, context)`, which
dispatches to `push()` or `poke_provisional()` based on
`context.candle.is_closed` — reusing an existing `MarketData` field (already
used by the live websocket path) rather than adding a new one to
`StrategyContext`. Both concrete strategies now call `self.track(...)`
instead of `series.push(...)` directly (9 call sites) — if you add a third
strategy, use `track()`, not `push()`, or its `Series` will silently commit
provisional ticks as if they were real bar closes.

**Two architecture proposals were reviewed and one was rejected — don't
re-propose it without re-reading why:** injecting `IIndicator` into `MACD`
via DI (so it's not hardcoded to `EMA`) was rejected — `EMA` isn't an
implementation detail of MACD, it's MACD's actual mathematical definition
(fast EMA − slow EMA, signal = EMA of that), swapping it produces a
different indicator, not "MACD with a pluggable internals." The parallel DRY
observation about `RSI` (Wilder's smoothing is mathematically an EMA variant
with `α=1/period`, currently hand-rolled instead of composed) was accepted
as legitimate, but deliberately *not* bundled into `BOT-042` — it's now its
own low-priority task,
[`BOT-101`](../Tasks/backlog/BOT-101_rsi_compose_generalized_smoothing.md).

**`BOT-076` §3.1/§3.2 — the engine core, done.** `RunRealtimeBacktestCommand`
has its own `tick_resolution: TimeFrame` field, independent of `interval` (a
strategy on `interval=5m` still gets evaluated every `tick_resolution`
inside the forming 5-minute bar — the user's original ask, verbatim: *"phải
chạy chiến thuật từng giây, cho dù tf có là 5 phút đi chăng nữa"*). **The
real bug found while wiring the replay loop, exactly where `BOT-076`'s own
doc warned it would be ("chỗ dễ sai nhất"):** the first version called
`on_forming_bar_tick()` unconditionally for every tick, including the tick
that closes a bar — that tick then got evaluated a *second* time via
`on_tick()` right after, with identical data, firing every real signal
twice on every single bar. Fixed by detecting "this tick's own close
reaches the bar boundary" (`tick.close_time >= bar_end`) and routing that
tick through `on_tick()` (commit) only — every other tick in the bar goes
through `on_forming_bar_tick()` (provisional) only, never both. If you touch
this loop, the regression test to run first is
`test_every_tick_is_evaluated_exactly_once_no_double_firing_on_bar_close`
in `tests/unit/application/use_cases/test_run_realtime_backtest.py`. A tick
gap between bars (missing data) force-commits the stale bar and logs a
`WARNING` rather than silently dropping it. Equity curve appends once per
committed bar, never per tick (so `max_drawdown` stays comparable to
Static's point set); signals fill immediately at the triggering tick's
price (`PaperExchange` is documented as agnostic to *when* a fill happens),
unlike Static's next-bar-open deferral — the deferral exists to prevent
look-ahead bias, and tick-level granularity removes the need for it.

**Still open on `BOT-076`:** §3.3 (UI — unlock the two tick-based Execution
Trigger Rule options in `OrderExecutionMenu.qml`, wire
`IThreadManager`/`CancellationToken` from `BackTestPresenter` the same way
Static's run already does, label results Realtime-vs-Static so the two
don't look identical with different meanings) and §3.5 (optional
play/pause/speed replay control — explicitly **not** required to call the
task done, see its own §3.5 note). Neither is started.

**Standing practice from this session, not just this task:** the user wants
logging added proactively during *all* feature dev (not only bug fixes), and
wants tests backed by log-based proof where the claim is really "did the
right decision/branch execute" — e.g. asserting on `caplog` output for a
commit/bar-close event, not just inferring it from the final result. Two of
`BOT-076`'s new tests do this explicitly; keep doing it going forward.

**Also this session:** `.agents/rules/bug-fix-rule.md` (new file — the full
bug-fix workflow, root cause first, log evidence for both repro and fix,
regression test before the fix at the correct tier, moved here from
fragments that used to live in `code-rule.md`/`commit-rule.md`) and
`TRACE`/`critical` log levels plus a `--debug` CLI flag
(`sagittarius_engine.infrastructure.logging.dev_verbosity.resolve_dev_verbosity()`
— generic engine behavior, not app-specific; `--debug` implies `--dev` and
additionally drops the threshold to `TRACE`). `BUG-013` (stale native
dispose callback crashing "Chạy Backtest" on the fallback-to-Python path)
is fixed — full writeup in
[`Tasks/bug_report/BUG-013.md`](../Tasks/bug_report/BUG-013.md); the
regression-test lesson worth repeating: a `Mock(spec=NativeBacktestChartHost)`
silently passed with **no fix applied at all**, twice, because the crash
lived inside a real method (`_assert_owning_gui_thread()`) a Mock never
executes — the working test uses a real native host at the Sanity tier.
Also: plain `QApplication.processEvents()` does not reliably flush a posted
`DeferredDelete` event in this environment — use
`QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)` to force a
widget's deferred deletion to actually happen inside a test.

## Longer-running open threads (not from this session, still true)

- **`BOT-023` (Dynamic Backtest) is CANCELLED** — do not resurrect it. Full
  rationale: [`Tasks/cancelled/BOT-023_dynamic_backtest_engine.md`](../Tasks/cancelled/BOT-023_dynamic_backtest_engine.md).
  The app has exactly **two** backtest engines: Static (`BOT-021` ✅) and
  Realtime (`BOT-076` ✅, now complete) — not three. Dynamic's only distinct
  value (play/pause/speed) became `BOT-076` §3.5, then was explicitly
  dropped by user decision when `BOT-076` was closed out.
- **`BUG-015`/`BUG-016` are Windows-only, still open, block `BOT-098F4`/`F5`/`F6C`/`F6D`
  from being called done.** `BUG-015`: native chart OHLCV/volume geometry
  randomly rebuilds (~75% of runs) on plain drag+wheel on real Windows 11
  D3D11 RHI — root cause narrowed to `sizeChanged` in `native_chart_item.cpp`
  possibly firing spuriously, **not confirmed**, needs `qDebug()` + rebuild
  on an actual Windows machine. `BUG-016`: `chart_migration_benchmark.py
  --desktop-contract` hangs completely on Windows, zero output, not
  root-caused at all. **If you're reading this because you just switched to
  a Windows machine — this is exactly the kind of investigation that needed
  real Windows access and couldn't be done on Linux.** See both bug reports
  in `Tasks/bug_report/` and the `[!NOTE]` block near the top of
  `Tasks/ROADMAP.md`'s "In Progress" section for the full context (including
  3 real probe-script bugs that were previously mis-blamed on "Wayland/
  software-RHI flaky" and have already been fixed).
- **Native chart was built/tested only for Backtest's "submit once per
  run/mode-change" pattern — not safe for a per-tick live chart (Dev Board)
  without new work.** `NativeBacktestChartHost`'s submission calls hard-assert
  the calling thread is the GUI thread (live ticks arrive on a background
  thread — no marshal step exists yet), and every submission is a
  full-replace snapshot, not incremental — at real tick frequency this would
  just relocate the CPU bottleneck the whole native migration exists to
  remove. `BOT-098F6`'s own scope doc excludes this for exactly this reason.
- **`BUG-009`/`BUG-010`** (cached-frame drag-preview widget shift, "Đồng bộ
  ngay" never clearing the missing-candles banner) are both **fixed and
  verified** — see their own files in `Tasks/bug_report/` for the final root
  causes, do not re-open unless a new, different symptom is reported.
- **`BOT-103`** (Realtime Backtest's tick loop causes real UI sluggishness
  via GIL contention — confirmed NOT literally running on the Qt UI thread,
  see this session's own entry above) is filed, not started, no remediation
  direction chosen yet.

## What this project is

**Sagittarius Elite Warrior** is a Binance trading bot: a Python desktop app
(PySide6 + QML/Qt Quick UI) built on **Clean Architecture**, itself built on
top of a separate shared framework, **Sagittarius Engine**. Two repos work
together:

- `Sagittarius-Engine/` — the **superproject**. Contains the shared
  `sagittarius_engine/` framework (DI container, `IThreadManager`,
  `ConfigManager`, the `pyside_mvc` extension with shared QML components
  like `StatefulButton.qml`). Its own `.agents/` playbook
  (`Sagittarius-Engine/.agents/PLAYBOOK.md` + `rules/`, `skills/`,
  `context/`) is generic — it doesn't know this app exists.
- `Sagittarius_Elite_Warrior/` — this **submodule**. The actual bot
  application: `src/domain/`, `src/application/`, `src/infrastructure/`,
  `src/presentation/ui/` (PySide6 screens, each a `<name>_presenter.py` /
  `<name>_view.py` / `<name>_view_model.py` MVP trio plus QML). This is
  where you'll do almost all real work.

## Installation & Dependencies

### Option 1: Install from GitHub Repository (Production / Shared)
```bash
pip install git+https://github.com/anhembedded/Sagittarius-Engine.git
```

### Option 2: Local Editable Installation (Development)
```bash
pip install -e Sagittarius-Engine
```

## Where the actual rules live (read these, don't guess)

- **`.agents/rules/code-rule.md`** (this folder) — the real, binding
  engineering rules for this submodule: No Hardcoding, SOLID, No Lazy Code
  (no `lambda` — write a named function instead), mandatory sanity tests
  for every new feature/screen, and the flat MVP-trio screen folder
  convention. Read it in full before writing any code — this summary is
  not a substitute.
- **`.agents/rules/bug-fix-rule.md`** (this folder) — the full bug-fix
  workflow: root cause first, regression test before the fix (confirmed
  failing for the right reason, at the correct test tier — see `BUG-013`'s
  own lesson in it about mocks silently hiding a non-reproduction), kept
  permanently after, then a `Tasks/bug_report/BUG-XXX.md` writeup. Read
  this before touching any reported bug.
- **`.agents/rules/install-rule.md`** (this folder) — installation guidelines and
  dependency setup for `sagittarius_engine` (GitHub URL install vs. local editable).
- **`.agents/rules/native-chart-rule.md`** — mandatory CMake build, Qt/PySide ABI,
  staging, and verification rules for `Sagittarius.NativeChart`. User commands
  live in `Docs/NATIVE_CHART_BUILD_AND_DEPLOY.md`.
- **`.agents/rules/logging-rule.md`** — where to place diagnostic logging so
  a single reproduce-and-send-log cycle can find a root cause: `"App."`
  namespace only (enforced by `tests/unit/test_logging_namespace_guard.py`),
  log decisions/fallbacks not just outcomes, one-shot environment lines for
  UI/rendering code, per-gesture (not per-event) summaries with pixel-scale
  numbers, and `--dev` now raises log level to DEBUG and writes a session
  file under `logs/`. Written after `BUG-009` cost three separate
  reproduce-and-send-log cycles to two different silent/misplaced-logging
  failures — see
  [`Tasks/reports/BUG-009_logging_and_test_gap_case_study.md`](../Tasks/reports/BUG-009_logging_and_test_gap_case_study.md)
  for the full timeline, including why the existing tests didn't catch the
  bug either (zero pixel-level assertions existed for the Python chart host
  before this session).
- **`.agents/AGENTS.md`** (this folder) — short SOLID recap plus the
  mandatory commit signature: every AI-authored commit ends with
  `Co-Authored-By: Antigravity <noreply@google.com>`.
- **`.agents/context/`** (this folder) — workload-specific, non-binding
  context. Read the matching file when working in that area; it records
  current facts, task order, and known hazards without duplicating rules.
  For Backtest lifecycle/FSM/async work, read
  `.agents/context/BOT-095_backtest_lifecycle.md` before editing code.
- **`../.agents/PLAYBOOK.md`** (superproject root) — generic AI working
  process (understand → load context → apply rules → pick a skill →
  execute → validate). Its context/rule/skill routing tables reference an
  `.ai/` path that doesn't actually exist in this repo (the real directory
  is `.agents/`) — a known stale reference, not something to "fix" as a
  drive-by unless asked.
- **`Tasks/ROADMAP.md`** — the live status board: completed vs. backlog
  task counts, and a table of every `BOT-XXX`/`BUG-XXX` task. Check this
  before assuming a feature is missing or unimplemented.
- **`.jules/bolt.md`, `.jules/palette.md`, `.jules/sentinel.md`** —
  running journals (critical learnings only, not logs) for three daily
  automation agents: Bolt (performance), Palette (UX/accessibility),
  Sentinel (security). `.jules/*.prompt.md` are their actual system
  prompts. If you're doing performance/UX/security work, read the
  matching journal first — it already has real, codebase-specific lessons.

## How to verify a change (real commands, ground truth)

From inside `Sagittarius_Elite_Warrior/`:

```bash
ruff check src tests
ruff format --check src tests
```

Full test suite, run from the **superproject root** (`PYTHONPATH=..` is
load-bearing — tests import this app as the `Sagittarius_Elite_Warrior`
package):

```bash
PYTHONPATH=.. QT_QPA_PLATFORM=offscreen pytest Sagittarius_Elite_Warrior/tests \
  --ignore=Sagittarius_Elite_Warrior/tests/integration/presentation/ui \
  --cov=Sagittarius_Elite_Warrior/src --cov-report=term-missing --cov-fail-under=80 -v
```

This is exactly what `.github/workflows/ci.yml` runs, and what
`scripts/ci-local.ps1` wraps (`-SanityOnly` / `-UnitOnly` for fast
subsets during a dev loop, `-Full` for the gated version above,
`-IncludeFlakyUi` to deliberately include the excluded UI-integration
suite). `tests/integration/presentation/ui/` is skipped by default in
`ci-local.ps1` because it has a known intermittent native Qt/PySide6
crash (tracked as `BOT-038`) — do not "fix" that as a drive-by, it's an
open investigation, and note the actual GitHub Actions workflow does
**not** exclude it (a real, unresolved discrepancy).

## Test-writing gotchas already discovered here

These cost real debugging time in previous sessions — check them before
you hit the same wall:

- **`Repeater`-instantiated QML items are invisible to `findChild()`.**
  `findChild()` walks the QObject tree; `Repeater` delegates only exist in
  the *visual* tree. Use this repo's own `qml_item` / `find_qml_item`
  pytest fixture (`tests/conftest.py`) instead.
- **A QML item's local `y`/`x` can look correct while it's actually
  clipped or off-screen.** Local coordinates are relative to the
  *immediate* parent and stay "correct" even past a clipped boundary. Use
  `item.mapToItem(root, 0, 0)` to get the real absolute position before
  comparing against a widget's bounds.
- **A single `qapp.processEvents()` is not enough** for anything that
  depends on QtQuick Layouts' deferred `implicitHeight`/`implicitWidth`
  recompute — it passes in isolation but flakes once run alongside the
  rest of the suite. Use `qtbot.waitUntil(condition, timeout=...)`.
- **`QQuickItem.ensurePolished()` only forces the polish job on the exact
  item you call it on.** If the pending recompute actually lives on a
  child `ColumnLayout`/`RowLayout`, calling it on the parent silently
  reads a stale value — find the actual item with the pending layout
  (`objectName` + `findChild`) and call it there.
- **Never put `onClicked` on a `MouseArea` nested inside a `Button`.**
  Real mouse clicks still work, but `qml_item(root, name).clicked.emit()`
  from a Python test finds nothing — the handler moved off the `Button`
  itself. This exact regression has happened twice (`BOT-057`, `BOT-083`).
- **`QQuickWidget`'s default resize mode is `SizeRootObjectToView`** — the
  root QML item's `implicitWidth`/`implicitHeight` are ignored unless
  Python explicitly reads them back and calls
  `setFixedHeight()`/`setMinimumHeight()`. A hardcoded pixel constant on
  the Python side is a red flag; prefer binding to the QML's own computed
  `implicitHeight`.
- **The bundled Basic-style `ScrollBar.qml`** renders invisible
  (`opacity: 0.0`) until `state === "active"`. `policy: AsNeeded` alone
  produces a scrollbar nobody sees; use a ternary between `AlwaysOn` (when
  content actually overflows) and `AlwaysOff`.
- **Popup bounds need an overlay assertion, not merely a click assertion.**
  For a modal hosted through `OverlayHost`, assert `overlay_host.overlay_size`
  from Python. It reads QML's real `Overlay.overlay` dimensions, which catches
  a popup trapped inside a short `QQuickWidget`; `find_qml_item()` alone cannot
  inspect Popup content reliably.

## Naming collision to watch for

`src/presentation/ui/assets/palette.py` defines a `Palette` class (the
app's real theme-color tokens, exposed to QML as `Theme.*`). This is
unrelated to the "Palette" UX agent in `.jules/palette.prompt.md` — don't
confuse the two when either is mentioned.

## When you're unsure

Search the repo first — `Tasks/ROADMAP.md`, existing tests, existing
screens under `src/presentation/ui/screens/` — before asking the user or
inventing behavior. Only ask if the answer genuinely isn't findable.
