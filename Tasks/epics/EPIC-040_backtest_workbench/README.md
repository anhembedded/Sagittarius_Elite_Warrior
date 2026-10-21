# EPIC-040 — Every bot kind is backtested in its own workbench, apart from the running bot

- **Status:** 🟢 `040A`–`040F` done 2026-10-20; `040G` parked by the owner 2026-10-20 (*"Epic này để đó, chưa cần làm"*, on the Proposed design record). Scaffolded on 2026-10-14 as a plan only (*"để đó, chưa cần làm"*); the owner un-parked it on 2026-10-20 (*"và làm thêm A cho tui đi"*), phase 1 first (`040A`–`040C`).
- **Repositories:** Elite
- **Origin:** The owner, 2026-10-14, on the Bots screen with a Spot Mainnet Grid running:
  - *"back test screen of the bot is no contribute when the bot run, so, could we move it to another tab with live chart? … back test could have another input parameters panel, that will not check the real equity of real account"*;
  - *"Cái này nên là common của mọi bot chứ nhỉ, k riêng gì bot grid"* ("this should be common to every bot, not just the Grid");
  - *"Bạn tạo epic luôn, viết từng task, đánh giá design từng task"* ("create the epic, write each task, assess each task's design");
  - later the same day, on bots that run a strategy: *"nó có nên là 1 loại bot riêng ko … nó sẽ có nhiều cái thao tác xử lý phức tạp hơn grid bot … nó cũng base vs bot grid"* ("should it be a bot kind of its own … it will need more complex handling than the Grid … it is also based on the Grid bot"), then *"gộp ý vừa rồi vào epic tách bot common"* ("merge that into the epic that makes bots common").
- **North star:** `Docs/HLD/11_desktop_workbench.md` (the workbench layout) and the kind seam of `EPIC-029D` / `EPIC-029F` (`ui/kinds/bot_backtest.py`, `ui/kinds/bot_kind_panel.py`). This epic completes that seam; it adds no new architecture style.
- **Decisions (optional):** §1, approved by the owner on 2026-10-20.
- **Dependencies:**
  - `EPIC-039`'s backtest pieces (`EPIC-039K`, `EPIC-039J`) are merged; this epic moves them, it does not change what they compute.
  - It is independent of `PRO-009` (colour and theme).

---

## 1. Decisions (approved by the owner, 2026-10-20)
The coordinator put the five decisions below to the owner, each summarised, with "approve all five" as its recommendation; the owner answered "Duyệt cả 5" (approve all five).
1. **Two centre tabs on the Bots screen.**
   - **Live** is the running bot: chart, Plan, Orders/Fills/Log.
   - **Backtest** is a sandbox: its own parameters and results.
   - The bottom Backtest dock tab goes away.
   - Mockups were shared in the coordinator session on 2026-10-14.
2. **The workbench is kind-neutral; a kind brings only its simulator and its editor.**
   - The period, Run/Cancel/Sync, the banner, the parameter diff, the equity, metrics and trades panes are written once.
   - A kind contributes a simulator behind a port, the `BotKindPanel` it already has, and optional extra figures.
3. **Sandbox parameters are a copy, never the bot's.**
   - They start from the selected bot's saved plan, and can be edited and reset.
   - A run never writes the bot, never sends an order and never reads the account balance.
   - A "copy to the bot's plan" action is out of scope (§5).
4. **The sandbox is judged by the symbol's rules, not by the account.**
   - Tick, step, minimum notional and fees still apply, so a replay cannot use orders the exchange would refuse.
   - Balance checks do not run: `BotKindInputs.account=None` already means "not checked"; the wording says "not checked in a simulation".
5. **A bot that runs a strategy is a kind of its own, on the shared bot shell, not built on the Grid.**
   - The Grid is a ladder of resting orders. A strategy bot reads candles, computes indicators, emits signals and manages one position. They share no execution logic to inherit.
   - What they share already lives in the bot shell, not in the Grid: the lifecycle and restart recovery, the venue profile (`EPIC-039`), the risk guard, exposure book, order pacer and checkpoint, the plan file (`BOT-176`), and this epic's workbench.
   - The strategy kind therefore brings only its `IBotKind` parts (`validate`, `overlay`, `executor_factory`) and its `IKindBacktester` adapter. The port of `040B` must fit it from the start (`040G`).

## 2. Goals — measurable
| Metric | Today (measured 2026-10-14 at `64e5510`) | When the epic is done |
| :--- | :-: | :-: |
| Lines of kind-neutral backtest UI living under `ui/kinds/grid/backtest/` (period, run state, equity, summary, trades) | about 1,190 lines in 8 files, all Grid-owned | the Grid keeps only its simulator adapter and extra figures; the rest sits once in the workbench. **Measured at `040F` (2026-10-20): 0 lines of page code; the folder holds 552 lines in 3 files, all offline fixtures (frames and sample replays); production source net −1,429 lines** |
| Where a backtest's parameters come from | the bot's on-screen plan (`kind_backtests.py:100`, `selected.edited or bot.config`) | the workbench's own copy; editing it never changes the bot |
| Lines a second kind (e.g. DCA) must add for a backtest UI | a full copy of the Grid page | one simulator adapter and one registration line |
| Where the backtest is shown | a bottom dock tab sharing height with Orders, Fills and Log | a centre tab the full width of the screen |
| Spot Grid replay results | the `EPIC-039B` oracle (600 plans) and the `EPIC-039K` tests | unchanged: same oracle, same tests, byte-identical figures |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-040A](completed/EPIC-040A_pin_grid_backtest_behaviour.md) | The Grid's backtest page is pinned by tests and preview frames before anything moves | Elite | None | 🟢 | ✅ Done (2026-10-20) |
| [EPIC-040B](completed/EPIC-040B_kind_neutral_backtest_contract.md) | One kind-neutral backtest result and simulator port; the Grid's replay answers through it | Elite | 040A | 🟡 | ✅ Done (2026-10-20) |
| [EPIC-040C](completed/EPIC-040C_sandbox_parameters.md) | Backtest parameters are a sandbox copy of a bot's plan, judged by the symbol's rules only | Elite | 040A | 🟡 | ✅ Done (2026-10-20) |
| [EPIC-040D](completed/EPIC-040D_backtest_workbench_shell.md) | A kind-neutral Backtest workbench: setup, run state and result panes, written once | Elite | 040B, 040C | 🟡 | ✅ Done (2026-10-20) |
| [EPIC-040E](completed/EPIC-040E_live_and_backtest_tabs.md) | The Bots screen has Live and Backtest centre tabs; the bottom Backtest tab is gone | Elite | 040D | 🟡 | ✅ Done (2026-10-20) |
| [EPIC-040F](completed/EPIC-040F_grid_on_the_workbench.md) | The Grid runs on the workbench and its duplicate backtest UI is deleted | Elite | 040E | 🔴 | ✅ Done (2026-10-20) |
| [EPIC-040G](incomplete/EPIC-040G_strategy_bot_kind.md) | A bot that runs a strategy is its own kind on the shared shell, backtested on the workbench with the same strategy code it runs live | Elite | 040B, 040F | 🔴 | ⏸ Parked by the owner (2026-10-20); design is a Proposed record |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 1. Pinned and contracted (040A–040C) | The Grid page's behaviour is pinned. The kind-neutral result and port exist with the Grid behind them. Sandbox parameters exist and are judged without the account | Characterisation tests and preview frames green on master. The 039B oracle unchanged. A test that editing the sandbox never touches the bot. Not run |
| 2. Workbench on screen (040D–040E) | The Backtest centre tab hosts the workbench for the selected bot's kind. Live keeps the chart, Plan and Orders/Fills/Log | Conformance suite at 1024×700, 1366×768 and 1920×1080. Preview frames for both tabs. The owner's look on Windows. Not run |
| 3. One copy (040F) | The Grid's page uses the workbench. The duplicate UI under `ui/kinds/grid/backtest/` is deleted | Every 040A test's behaviour is pinned by a workbench test; they could not pass *unchanged*, because the page they drove is deleted, so each was ported or matched (`040F`'s implementation notes list them), and the `039B` oracle and `039K` tests are untouched. Line count recorded against §2. Owner's look at the before/after frames: not yet |
| 4. Second kind (040G) | A strategy bot runs on Testnet with the shell's lifecycle and is backtested on the workbench, with no change to kind-neutral code beyond registration | Backtest and live give the same signals on the same candles (parity test). Restart recovery after warm-up. Testnet run. Not run |

## 5. Out of scope
- **Copying sandbox parameters into a bot's plan.** That is a later task. It must pass Start's checks on a stopped bot; it is never a shortcut from a simulation to real money.
- **The DCA kind.** The epic makes it cheap; it does not add it. The strategy (signal) kind is in scope as `040G`, moved here from `EPIC-029L` at the owner's request.
- **Simulator changes.** The Grid and Futures replays compute what they compute today.
- **Colour and theme.** That is `PRO-009`.
- **Showing the backtest and the live chart side by side.** A tab can later be detached into its own window (a Qt dock), if wanted.

## Follow-ups (deferred from review, not dropped)
Found while delivering `040D`–`040F` and the interval picker; none blocks a child, each needs a task or a decision.
| # | Follow-up | Found in | Needs |
| :-- | :--- | :--- | :--- |
| F1 | **A Bots-mode menu command for the timeframe picker.** The Bots mode has no command named "More timeframes…", so the pinned timeframe actions of the Live chart's toolbar and of the workbench's interval toolbar are not reachable from the menu bar (`ui-presentation-rule.md` §6). The workbench's interval buttons take Tab focus meanwhile (PR #642). Pattern: Market and Backtest contribute `chart_commands` with a prefix and menu path and follow the chart in front (`ChartCommandMirror.follow_chart`). | PR #642, review round 1 | **Done in [BOT-211](../../completed/BOT-211_a_bots_mode_menu_command_for_the_timeframe_picker.md)** (2026-10-21). A BOT task |
| F2 | **A conformance case with a backtestable bot selected.** `test_workbench_conformance.py` measures the Bots mode with no bot selected, so the workbench page (built on `follow()` with a bot) and its toolbars are never in the suite. The case seeds a bot, shows the Backtest tab, and measures menus, toolbars, size and scroll areas at the three window sizes. It would have caught F1. | PR #642, review round 1 | **Done in [BOT-212](../../completed/BOT-212_a_conformance_case_with_a_backtestable_bot_selected.md)** (2026-10-21). A BOT task |
| F3 | **The Replay chart's own timeframe row.** The result chart keeps its pinned `1m 5m 15m 1h 1d` row beside the new interval picker: a second chooser that changes nothing the person ran, offers `1d`, and its empty text says "Pick another timeframe". Hide it for the result chart, or make it follow the interval. | PR #642, the author and its reviewer | **Done in [BOT-213](../../completed/BOT-213_the_replay_chart_hides_its_own_timeframe_row.md)** (2026-10-21). Decided by the coordinator for the owner, 2026-10-20 (*"bạn tự quyết"*): the result chart hides its own timeframe row, because the replay is at the interval that was run and a second chooser changes nothing the person ran. A BOT task |
| F4 | **Unpinning every interval in the picker's dialog** leaves the interval row with only "More timeframes…" while Run still replays the chosen one. Refuse the last unpin, or name the interval in the status. | PR #642, review round 1 (optional) | **Done in [BOT-214](../../completed/BOT-214_the_interval_picker_keeps_the_interval_run_replays_pinned.md)** (2026-10-21). Decided by the coordinator for the owner, 2026-10-20 (*"bạn tự quyết"*): the dialog refuses to unpin the last interval, so the row always shows what Run replays. **2026-10-21, coordinator for the owner: the rule is that the interval Run replays stays pinned and choosing an interval pins it** (refusing the last pin alone left the row showing an unchecked `1h` while Run replayed 15m). A BOT task |
| F5 | **With a bot selected, the Bots table, the Ladder and the venue combo run past their edges** at 1024×700 and 1366×768 (the Ladder at 1920×1080 too). Found by F2's first run; its case leaves the two checks out until the bug is fixed and a test fails the day it is. | F2 / PR #661 | [BUG-245](../../bug_report/incomplete/BUG-245_with_a_bot_selected_the_bots_table_the_ladder_and_the_venue_combo_run_past_their_edges.md); the coordinator schedules the fix |
| F6 | **The Backtest tab's setup column draws its text over itself** at 1024×700 and 1366×768, and no check reads overlap. Also seen in the same frames: the interval row overflows into `››` at 1366×768 and shows only `1m` while 15m is chosen (F4's symptom by layout), and the result chart's card is captioned "Live Chart: Backtest". | PR #661 review, round 1 · fixed 2026-10-21 by BOT-218: the setup column is the Live Plan's `PlanColumn`, one scroll | [BUG-246](../../bug_report/completed/BUG-246_the_backtest_tabs_setup_column_draws_its_text_over_itself_at_1024x700_and_1366x768.md) |

## Resume

*Written 2026-10-20 by the author session of `040A`–`040C`, for the session that takes `040D`–`040G`; brought up to date by the `040D` pull request. The owner asked for all of EPIC-040.*

**Where it stands.** Phase 1 is done: `040A` ([#624](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/624), merged `e6551b2`), `040B` ([#627](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/627), merged `6c5f05a`) and `040C` ([#628](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/628), merged `dd3897f`); `040D` (the workbench page, `ui/backtest_workbench/`) is in the next pull request. Nothing is on screen in the app yet: the Grid's own Backtest page is unchanged, `040E` hosts the workbench and `040F` replaces the Grid's page.

**Where `040D` starts.** Read, in order: §1 here; [`040D`](completed/EPIC-040D_backtest_workbench_shell.md); the *Implementation notes* of the three completed children (their "Findings" paragraphs are the hand-over); `Docs/MODULES/bots/05-building-blocks.md` ("The kind's backtest") and `08-concepts.md` (the sandbox plan). The code to build on:
- `bots/domain/backtest/` — `BacktestOutcome` and its records, `StopCause`, `BacktestAnswer`, `SandboxPlan`; `bots/contracts/i_kind_backtester.py` — `IKindBacktester`, `KindBacktestRequest`; `IBotKind.backtester()` finds a kind's backtest through the catalog.
- `bots/ui/backtest/` — `SandboxSession` (copy the saved plan, ask before discarding edits), `judge_sandbox`, `sandbox_line`.
- The safety net was `test_grid_backtest_states.py` and `preview_frames.py` (thirteen frames); `040F` carried every state to the workbench (`test_workbench_frames.py`) and deleted both, with the Grid page (about 1,190 lines) and its hosting; `040E` replaced `kind_backtests.py`.

**What each child left for a later one** (also written in that child's file):

| For | Left by | What |
| :-- | :-- | :-- |
| `040D` | 040B | The neutral dispatching query (kind id and `KindBacktestRequest` in, `BacktestAnswer` out, resolving `IBotKind.backtester()` from the catalog) and its coordinator. Map `FigureTone` to the meaning colours (`Tone`; the Grid sets none). Build the trades pane by pairing the labelled `fills` (the outcome has no trade record). Mark `StopCause` on the chart. |
| `040D` | 040C | The sandbox editor is a second `BotKindPanel`; it must **not** be bound to the Bots menu's kind commands (`kind_command_binding.py` acts on the selected bot's panel) and takes `set_plan_facts(None, risk)`. Bind the "discard your edits?" question to `SandboxSession.confirm_switch` / `keep_current`. Say whose fees a run charges (the account's tier). |
| `040E` | 040A | The tabbed centre. The Engine's workbench shell takes any central widget (`sagittarius_engine/extensions/pyside_mvc/workbench/workbench_shell.py`), and `bots_view.py` already uses a stock `QTabWidget`, so a stock `QTabWidget` in the centre needs no Engine change; confirm it when `040E` starts. |
| `040F` | 040A | The status line: `GridBacktestView.show_idle("")` writes no status, so "Backtest done." stays after another bot is selected, "Backtesting…" stays after a mid-run switch (Run on, Cancel off), and "Select a bot…" stays once the page is ready. One cause; fix and pin it (the tests leave those states unasserted on purpose). Also "No candles are stored for  at 15m." before the first run (an empty symbol), and a frame for a late *refusal* after a mid-run switch. | **Done in `040F`:** pinned on the workbench by `test_a_ready_page_says_nothing_stale` and the late-refusal test; the page they were fixed on is deleted. |
| `040F` | 040B | Drop the Grid's duplicate records (`PriceBar`, `EquityPoint`, `BacktestFill`, `BacktestProvenance`, `DataWindow`; `BacktestBar` repeats `PriceBar`) once the 039B oracle's imports are retargeted. | **Done in `040F`:** `DataWindow` and `BacktestProvenance` were copies and are dropped; `BacktestFill`, `EquityPoint` and `PriceBar` differ in shape and stay (the oracle asserts on them). |
| `040G` | 040B | A trade record beside `fills`, or the workbench pairs entries and exits; the assertion that nothing before `start` is reported (the stub test cannot make it); a `StopCause` member such as a signal exit. |

**Open questions, with a recommendation.**
1. **§1's decisions.** Resolved: the owner approved all five on 2026-10-20 (§1 records it), and `TRACKING.md` no longer lists them as a blocker.
2. **Does the sandbox read the planner market the live panel reads, or a terms-only read?** Resolved in `040D`: it reuses `selected.market` (no new read, the same numbers the live plan is judged by) and the page says a run charges the account's fees as read now (`ui/backtest_workbench/source_line.py`); a terms-only read waits for an owner objection.
3. **`040G` is 🔴 (real orders from strategy code) and its per-file design is written when it starts.** *Recommend:* write a decision record from `.claude/templates/decision.md` (the strategy reference and version, where warm-up comes from, the position executor's scope, fault isolation) and send it to the coordinator before any `040G` code; the Engine, dependencies and config stay untouched without asking.

**Working notes for the next session.**
- The environment is ephemeral: set up `.venv`, the engine pin and `pwsh` as `install-rule.md` §2b says; `PYTHONPATH=..` and `QT_QPA_PLATFORM=offscreen` for tests. Run the commit tier, `tests/unit/architecture`, `tests/unit/modules/bots` and `tests/unit/presentation` before each push (about 5 minutes); they caught three ratchets that the focused tests do not: `ANN401` (no `Any` in a new signature), the member-name duplication ratchet (a new class member named like a member of another UI package; rename it) and the display-formatting guard (no `strftime` or format spec in UI code).
- Check a test by mutation: stage first (`git add`), mutate, run, `git checkout -- <file>`; a new untracked file cannot be restored that way. Reviewers found two surviving mutants in `040B` that the author's own checks missed, so probe the field-by-field mappings.
- One reviewer session per pull request (on a different model from the author's, never one `ONBOARDING.md` §7 excludes), spawned in the turn that pushes; push once per round with every fix; read both `gate (Unit)` and `gate (Rest)` job logs yourself even when the reviewer says green, then send READY with the full sha and the review comment link.

## Notes (newest first)
- **2026-10-20** — `040E` done: the Bots screen's centre has Live and Backtest tabs and the bottom Backtest dock and `_BacktestSlot` are gone; one workbench per venue; the tab is off, never hidden, for a kind with no backtest. The Grid's own page is unhosted and waits for `040F` to delete it; the workbench's results became tabs to keep the mode within a 1024×700 window.
- **2026-10-20** — `040D` done: one workbench page for any kind (`ui/backtest_workbench/`), driven by `RunBacktestQuery`, with the Grid registered as the only kind in its tests and a stub strategy kind proving no Grid is needed. It is not on screen until `040E`; `040F` deletes the Grid's own page. The §1 decisions are recorded as approved.
- **2026-10-20** — `040C` done, and with it phase 1 (`040A`–`040C`): the frozen `SandboxPlan`, the session rule (copy the saved plan; ask before discarding edits), judging by the kind's `validate` with no account, and a guard plus an execution test that the sandbox sends no command. Nothing shows a sandbox on screen until `040D`; the coupling to settle there is recorded in the child.
- **2026-10-20** — `040B` done: the kind-neutral `BacktestOutcome`, the `IKindBacktester` port found through `IBotKind.backtester()`, and the Grid's adapter. The neutral types are new records mapped from the Grid's, not moved, so the 039B oracle and 039K tests keep their imports; `FundingRequirement` moved to the domain. Nothing draws the outcome until `040D`.
- **2026-10-20** — `040A` done: thirteen preview frames and one test per state, no behaviour changed. It found three status-line gaps (one cause) the Grid page has today; they are recorded in the child for `040F`.
- **2026-10-20** — Un-parked by the owner. `040A`, then `040B` and `040C` one after the other, each from master once the last is merged; `040D`–`040G` wait for a later phase.
- **2026-10-16** — The bots design is now the folder [`Docs/MODULES/bots/`](../../../Docs/MODULES/bots/README.md) (`EPIC-041E`), which replaces `bots.md`. A child changes the file that holds the fact it changes, and its pull request answers "Design in step" (`commit-rule.md` §1); its `Planned` rows name `040B`, `040C` and `040G`.
- **2026-10-14** — Every child updates the views of `Docs/MODULES/bots.md` it changes, through its "Docs touched" section. The skeleton comes from [`EPIC-041A`](../EPIC-041_documentation_standard/completed/EPIC-041A_docs_skeleton.md), which runs first.
- **2026-10-14** — Decision 5 and `040G` added: the strategy bot is a kind of its own on the shared shell, taken from `EPIC-029L`. `040B` now requires its port to fit that kind.
- **2026-10-14** — Epic scaffolded from the owner's request. Six children, each with its design assessed. Not started, as asked.
