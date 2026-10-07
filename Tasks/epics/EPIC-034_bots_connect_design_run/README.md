# EPIC-034 — A bot connects to its account, is designed against every constraint, then runs

- **Status:** 🔵 Planned
- **Repositories:** Elite
- **Origin:** the owner, 2026-10-07, on a screenshot of a new Grid bot that could not start: *"bot không start được tui cũng không biết nó đang thiếu gì. đánh giá lại, làm feature này cho nó hợp lý nhé"* (the bot does not start and I cannot tell what it lacks; re-assess and make this feature sensible). Then: *"bot phải có state là đã kết nối được với account, có thể get thông tin tài khoản … sau đó người dùng mới xem chart, và set các param, các param đảm bảo được assert đúng với các ràng buộc"* (a bot must first reach a state where it is connected to the account and can read the account information; only then does the user see the chart and set the parameters, and the parameters are asserted against the constraints). And: *"giờ tui đưa key mainnet thì nó phải get được thông tin của tôi, đó là 1 milestone trong epic"* (when I give a mainnet key it must read my information; that is a milestone of this epic). The proposal the owner reviewed: https://claude.ai/artifact/G6GsKHZLoAr6FFz5SPGDsV.
- **North star:** [`Docs/SPEC/SPEC-014_run_a_grid_bot.md`](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) and [`Docs/HLD/11_desktop_workbench.md`](../../../Docs/HLD/11_desktop_workbench.md) §11.2; both are updated by the child that changes the flow they describe.
- **Decisions:** [`DECISION_2026-10-07_bots_mode_flow.md`](DECISION_2026-10-07_bots_mode_flow.md) — D1–D10.
- **Tracking:** [`TRACKING.md`](TRACKING.md).
- **Dependencies:** None to start. [`EPIC-026`](../EPIC-026_road_to_real_money/README.md)'s D6 was cancelled by the owner on the same day, which is what lets `EPIC-034E` read a mainnet account before that epic's soak.

---

## 1. Decisions already made
1. A bot goes through three steps, each unlocking the next: **Connect** (the account is read), **Design** (chart and parameters, every constraint asserted), **Run** (D1, owner).
2. Every venue with a usable key is on; the Spot and Futures toggles in Tools → Options leave (D2, owner).
3. The trading ON/OFF switch leaves; its reconciliation runs inside Start, arm and a manual order instead (D3, owner chose option A).
4. A mainnet key is read, never traded: a read-only account source that is not a `TradingVenue` (D4, owner milestone).
5. D5–D10 (key permissions, Connect runs by itself, blocking versus advisory constraints, Save and Start, a live chart for a draft, the mainnet secret in the keyring) were accepted as recommended.

## 2. Goals — measurable
| Metric | Today (measured 2026-10-07) | When the epic is done |
| :--- | :-: | :-: |
| Reasons that can disable Start and are shown before the click | 1 of 9 (the plan's verdict) | all |
| Start refusals that appear only after the click | 5 (trading off, venue, lease, budget, other bot) | 0 |
| Places that show a venue as its raw identifier (`spot_testnet`) | 3 | 0, guarded |
| Bot-chart messages that reach the user | 0 of 4 | 4 of 4 |
| Plan constraints that use the real account balance before Start | 0 | capital, base inventory, key permission |
| Steps between a new key and an order: Options venue tick, restart, Enable trading, Start | 4 | 1 (Start) |
| A mainnet read-only key shows the real balances | no | yes, with withdrawal keys refused |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| [EPIC-034C](completed/EPIC-034C_trading_switch_folded_into_actions.md) | The trading switch leaves; Start, arm and a manual order reconcile and open the order session themselves | Elite | EPIC-034B | 🔴 | ✅ Done (2026-10-07) |
| [EPIC-034E](incomplete/EPIC-034E_mainnet_read_only_account.md) | A mainnet key is read, never traded: balances, fees and key permissions; withdrawal keys refused | Elite | EPIC-034D | 🔴 | 🟡 In progress (the owner's check remains) |
| [EPIC-034B](completed/EPIC-034B_every_venue_with_a_key_is_on.md) | Every venue with a usable key is on; the Options venue toggles and the restart leave | Elite | None | 🟡 | ✅ Done (2026-10-07) |
| [EPIC-034D](completed/EPIC-034D_connect_step.md) | Connect: one account snapshot per venue gates the chart and the plan | Elite | EPIC-034A | 🟡 | ✅ Done (2026-10-07) |
| [EPIC-034F](completed/EPIC-034F_design_step_constraints.md) | Design: every constraint is a named assertion, shown on its field, with the account's numbers | Elite | EPIC-034D | 🟡 | ✅ Done (2026-10-07) |
| [EPIC-034G](completed/EPIC-034G_chart_live_state.md) | The chart states whether it is live, and the user starts and stops it | Elite | EPIC-034A | 🟡 | ✅ Done (2026-10-07) |
| [EPIC-034H](completed/EPIC-034H_run_step_readiness.md) | Run: one readiness query serves the screen and the Start handler; Save and Start | Elite | EPIC-034C, EPIC-034F | 🟡 | ✅ Done (2026-10-07) |
| [EPIC-034I](completed/EPIC-034I_every_live_chart_goes_through_the_shared_live_chart.md) | Every chart that shows live market prices is built on the shared live chart: an architecture guard | Elite | EPIC-034G | 🟢 | ✅ Done (2026-10-07) |
| [EPIC-034A](completed/EPIC-034A_bots_mode_says_what_it_knows.md) | The Bots mode says what it already knows: venue titles, the chart's messages, why an action is disabled | Elite | None | 🟢 | ✅ Done (2026-10-07) |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 1 — Say what it knows | `EPIC-034A` merged: no raw venue identifier, the bot chart's messages and empty state visible, a disabled action's reason visible | Its tests; a screenshot of a new bot on the owner's display. Not run |
| 2 — Connect | `EPIC-034B`, `034C`, `034D` merged: a key is enough to reach the Connect step; no Enable trading switch | The SPEC journeys; the owner's Testnet run. Not run |
| Milestone — mainnet read-only | `EPIC-034E` merged: the owner's mainnet read-only key shows the real balances; a withdrawal key is refused | The architecture guard; the owner's manual check. Not run |
| 3 — Design and run | `EPIC-034F`, `034G`, `034H` merged: Start is reachable only through the three steps, every reason shown before the click | The SPEC-014 journeys; the desktop E2E. Not run |

## 5. Out of scope
- Trading on mainnet: [`EPIC-026`](../EPIC-026_road_to_real_money/README.md) (its D3 and D5 still hold).
- Futures grids and other bot kinds: `EPIC-029K` / `EPIC-029L`.
- The historical-tick backtest on Futures: [`BUG-166`](../../bug_report/incomplete/BUG-166_historical_tick_backtest_cannot_run_on_futures_and_its_execution_dialog_misleads.md) and [`BOT-168`](../../backlog/BOT-168_true_futures_one_second_ticks_for_the_realtime_backtest.md).

## Notes (newest first)
- **2026-10-07** — Epic, decision record and eight sub-tasks written from the owner's proposal review and decisions.
