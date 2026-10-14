# EPIC-040 — Every bot kind is backtested in its own workbench, apart from the running bot

- **Status:** 🔵 Planned. Scaffolded on 2026-10-14; the owner asked for the plan only: *"để đó, chưa cần làm"* ("leave it there, do not start yet").
- **Repositories:** Elite
- **Origin:** The owner, 2026-10-14, on the Bots screen with a Spot Mainnet Grid running:
  - *"back test screen of the bot is no contribute when the bot run, so, could we move it to another tab with live chart? … back test could have another input parameters panel, that will not check the real equity of real account"*;
  - *"Cái này nên là common của mọi bot chứ nhỉ, k riêng gì bot grid"* ("this should be common to every bot, not just the Grid");
  - *"Bạn tạo epic luôn, viết từng task, đánh giá design từng task"* ("create the epic, write each task, assess each task's design").
- **North star:** `Docs/HLD/11_desktop_workbench.md` (the workbench layout) and the kind seam of `EPIC-029D` / `EPIC-029F` (`ui/kinds/bot_backtest.py`, `ui/kinds/bot_kind_panel.py`). This epic completes that seam; it adds no new architecture style.
- **Decisions (optional):** pending the owner; see §1.
- **Dependencies:**
  - `EPIC-039`'s backtest pieces (`EPIC-039K`, `EPIC-039J`) are merged; this epic moves them, it does not change what they compute.
  - It is independent of `PRO-009` (colour and theme).

---

## 1. Decisions proposed (pending the owner)
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

## 2. Goals — measurable
| Metric | Today (measured 2026-10-14 at `64e5510`) | When the epic is done |
| :--- | :-: | :-: |
| Lines of kind-neutral backtest UI living under `ui/kinds/grid/backtest/` (period, run state, equity, summary, trades) | about 1,190 lines in 8 files, all Grid-owned | the Grid keeps only its simulator adapter and extra figures; the rest sits once in the workbench |
| Where a backtest's parameters come from | the bot's on-screen plan (`kind_backtests.py:100`, `selected.edited or bot.config`) | the workbench's own copy; editing it never changes the bot |
| Lines a second kind (e.g. DCA) must add for a backtest UI | a full copy of the Grid page | one simulator adapter and one registration line |
| Where the backtest is shown | a bottom dock tab sharing height with Orders, Fills and Log | a centre tab the full width of the screen |
| Spot Grid replay results | the `EPIC-039B` oracle (600 plans) and the `EPIC-039K` tests | unchanged: same oracle, same tests, byte-identical figures |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-040A](incomplete/EPIC-040A_pin_grid_backtest_behaviour.md) | The Grid's backtest page is pinned by tests and preview frames before anything moves | Elite | None | 🟢 | Planned |
| [EPIC-040B](incomplete/EPIC-040B_kind_neutral_backtest_contract.md) | One kind-neutral backtest result and simulator port; the Grid's replay answers through it | Elite | 040A | 🟡 | Planned |
| [EPIC-040C](incomplete/EPIC-040C_sandbox_parameters.md) | Backtest parameters are a sandbox copy of a bot's plan, judged by the symbol's rules only | Elite | 040A | 🟡 | Planned |
| [EPIC-040D](incomplete/EPIC-040D_backtest_workbench_shell.md) | A kind-neutral Backtest workbench: setup, run state and result panes, written once | Elite | 040B, 040C | 🟡 | Planned |
| [EPIC-040E](incomplete/EPIC-040E_live_and_backtest_tabs.md) | The Bots screen has Live and Backtest centre tabs; the bottom Backtest tab is gone | Elite | 040D | 🟡 | Planned |
| [EPIC-040F](incomplete/EPIC-040F_grid_on_the_workbench.md) | The Grid runs on the workbench and its duplicate backtest UI is deleted | Elite | 040E | 🔴 | Planned |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 1. Pinned and contracted (040A–040C) | The Grid page's behaviour is pinned. The kind-neutral result and port exist with the Grid behind them. Sandbox parameters exist and are judged without the account | Characterisation tests and preview frames green on master. The 039B oracle unchanged. A test that editing the sandbox never touches the bot. Not run |
| 2. Workbench on screen (040D–040E) | The Backtest centre tab hosts the workbench for the selected bot's kind. Live keeps the chart, Plan and Orders/Fills/Log | Conformance suite at 1024×700, 1366×768 and 1920×1080. Preview frames for both tabs. The owner's look on Windows. Not run |
| 3. One copy (040F) | The Grid's page uses the workbench. The duplicate UI under `ui/kinds/grid/backtest/` is deleted | The 040A tests pass unchanged against the new page. Line count recorded against §2. Not run |

## 5. Out of scope
- **Copying sandbox parameters into a bot's plan.** That is a later task. It must pass Start's checks on a stopped bot; it is never a shortcut from a simulation to real money.
- **New bot kinds** (DCA, Signal). The epic makes them cheap; it does not add them.
- **Simulator changes.** The Grid and Futures replays compute what they compute today.
- **Colour and theme.** That is `PRO-009`.
- **Showing the backtest and the live chart side by side.** A tab can later be detached into its own window (a Qt dock), if wanted.

## Notes (newest first)
- **2026-10-14** — Epic scaffolded from the owner's request. Six children, each with its design assessed. Not started, as asked.
