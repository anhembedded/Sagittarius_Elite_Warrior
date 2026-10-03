# EPIC-029 — A Bots tab, and one Grid bot trading on Spot Testnet as fast as it can be done right

- **Status:** 🔵 Planned. `PRO-006` was accepted by the user on 2026-10-03. The ADR is Proposed and
  revised after review round 1. It waits for the re-review and the user's answers to D6, D21 and
  O1–O5.
- **Repositories:** Elite. No Engine change is expected.
- **Origin:** [`PRO-006`](../../proposal/PRO-006.md). The user's acceptance, 2026-10-03: *"Oki,
  duyệt, nhớ design đúng nha, ko lazy design"* ("OK, approved; get the design right, no lazy
  design").
- **North star:** [`PRO-006`](../../proposal/PRO-006.md) §4 for the shape, and
  [`Docs/HLD/11_desktop_workbench.md`](../../../Docs/HLD/11_desktop_workbench.md) for the place a new
  tab takes.
- **Decisions:** [`DECISION_2026-10-03_bots_module_and_grid_bot.md`](DECISION_2026-10-03_bots_module_and_grid_bot.md)
  (D1–D21, O1–O5; Proposed; revised after review round 1).
- **Tracking (Gantt, PR matrix):** [`TRACKING.md`](TRACKING.md).
- **Dependencies:**
  - Builds on [`EPIC-027`](../EPIC-027_spot_trading_and_spot_backtest/README.md) and
    [`EPIC-028`](../EPIC-028_futures_and_spot_trading_desks/README.md), both ✅: the Spot adapters,
    the user data stream, per-venue ports, LIMIT GTC, and the order-entry terms.
  - Exchange-side stops wait for [`EPIC-026K`](../EPIC-026_road_to_real_money/README.md).
  - Mainnet stays behind `EPIC-026`'s gates.

---

## 1. Decisions already made

The user decided these on 2026-10-03 (`PRO-006` §2.1, 🟢):

1. Signal and Grid/DCA bots share one common shell, and **Grid comes first**.
2. **Many bots by design**, with one Grid bot on a fast track.
3. "Trading for real" means **Spot Testnet**.
4. **Every bot has its own chart.**
5. **The parameters belong to the user.** The bot judges them and never fixes them.
6. **The backtest runs in parallel** with the live bot, and is required before mainnet.
7. **The desks become manual only, after the fast track.**
8. A manual order on a bot's symbol is **refused, with a takeover**.

The ADR proposes the design that follows (D1–D20). The ones that shape the plan:

- **D1:** a new `bots` module.
- **D5:** client order ids carry a bot tag.
- **D6:** an owner budget instead of the signal limits, which today refuse a ladder's second order.
  It needs the user.
- **D7:** a switch event.
- **D9:** one actor per bot.
- **D12:** a bot never places an order at app start.
- **D14:** a fill rule of trade-through by one tick.
- **D15:** one shared live chart, with `ChartCard` left frozen.

## 1.1 What the tree already has (measured 2026-10-03, `ff2a7f9a`)

| Capability | Where |
| :--- | :--- |
| LIMIT GTC and quote-sized market buy on Spot | `trading/adapters/binance/spot/spot_order_payload_mapper.py:50-52,98-104` |
| Per-venue order submission and cancel | `trading/contracts/i_order_submission.py:243-306` |
| Fill and end events with fees | `trading/contracts/events/order_filled_event.py:41-56`, `order_ended_event.py:82-85` |
| Symbol filters and maker/taker rates | `trading/contracts/i_order_entry_terms.py:117`, `commission_rate.py:44-46` |
| Symbol lease by owner | `trading/contracts/i_trading_session.py:134-153` |
| History and live candles for a chart | `market_data/contracts/i_historical_klines.py:48-95`, `IMarketStream` |
| 1-second klines (the finest stored data) | `backtesting/application/run_historical_tick_backtest/handler.py:118-143` |

## 1.2 What the tree does not have

- **No ladder can run today.** The second order on a symbol is refused by
  `max_positions_per_symbol=1` and `min_order_interval=60s`
  (`trading/contracts/trading_limits.py:89-94`). On Spot, nothing ever clears the mark.
- **Order identity and signals:**
  - a caller cannot tag a client order id;
  - no event says an order was accepted;
  - no event says trading was disabled or Emergency-Stopped.
- **The Spot cancel event may carry the cancel request's id**, not the original order's (ADR §1.2,
  ❓).
- **Charting and indicators:**
  - no horizontal price lines on `ChartCard`, which is frozen at 881 lines;
  - no ATR, no Bollinger Bands;
  - no buy-and-hold comparison.
- **Bots:** no bot entity, no Bots screen, and no backtest of resting orders.

## 2. Goals — measurable

| Metric | Today (measured 2026-10-03) | When the fast track is done | When the epic is done |
| :--- | :-: | :-: | :-: |
| Resting LIMIT orders one owner can keep on one symbol | 1 | grid_count + 1, within its budget | the same, per bot |
| Bots that can run at once | 0 | 1 | one per symbol |
| Grid bots trading on Spot Testnet | 0 | 1, soaked for 24 h or more with restarts and an Emergency Stop | Spot and Futures |
| Parameter checks with a verdict and a reason | 0 | about 9 Grid checks: 3 refusals (certain loss or certain rejection), the rest warnings | per kind |
| Charts drawing a bot's own indicators | 0 | 1 overlay drawing 3 surfaces | per kind |
| Grid backtests on real data, stating their fill rule | 0 | yes, in parallel | required before mainnet |
| Desks with a strategy card | 2 | 2 | 0 (manual only) |

## 3. Sub-tasks, ordered by risk

| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-029A](incomplete/EPIC-029A_trading_seams_for_bots.md) | Trading seams: client order tag, owner budget with an owner book derived from exchange evidence, switch event, Spot cancel id, fake exchange LIMIT matching | Elite | D6, O1, O5 (for the budget) | 🔴 | Planned |
| [EPIC-029E](incomplete/EPIC-029E_live_grid_executor.md) | The live Grid executor: actor, levels, start, fill, stop, stop loss and take profit, Halted, reconciliation | Elite | 029A, 029B, 029C, O2, O3 | 🔴 | Planned |
| [EPIC-029K](incomplete/EPIC-029K_grid_on_futures.md) | Grid on Futures: leverage, liquidation guard, modes *(after the fast track)* | Elite | 029H | 🔴 | Planned |
| [EPIC-029B](incomplete/EPIC-029B_bots_module_entity_and_store.md) | The `bots` module: entity, kind seam, lifecycle FSM, store | Elite | None | 🟡 | Planned |
| [EPIC-029D](incomplete/EPIC-029D_grid_backtest.md) | Grid backtest: ladder simulator, fill rule, buy-and-hold *(parallel)* | Elite | 029C, 029G | 🟡 | Planned |
| [EPIC-029F](incomplete/EPIC-029F_bots_tab.md) | The Bots tab: list, shell, Grid panel with verdicts, dialogs, SPEC-014 | Elite | 029B, 029C, 029G, O4 (built against the use-case commands; the end-to-end run with 029E is checked in 029H) | 🟡 | Planned |
| [EPIC-029G](incomplete/EPIC-029G_bot_chart.md) | The bot chart: shared live chart, price levels, one Grid overlay for three surfaces | Elite | 029C | 🟡 | Planned |
| [EPIC-029H](incomplete/EPIC-029H_spot_testnet_grid_soak.md) | Spot Testnet soak and report *(the fast track's goal)* | Elite | 029D, 029E, 029F, 029G | 🟡 | Planned |
| [EPIC-029I](incomplete/EPIC-029I_desks_manual_only.md) | Desks manual only, bot badge, takeover, SPEC-010 *(after the fast track)* | Elite | 029H | 🟡 | Planned |
| [EPIC-029J](incomplete/EPIC-029J_many_bots.md) | Many bots, one per symbol *(after the fast track)* | Elite | 029H | 🟡 | Planned |
| [EPIC-029L](incomplete/EPIC-029L_signal_and_dca_kinds.md) | Signal and DCA kinds *(after the fast track)* | Elite | 029I, 029J | 🟡 | Planned |
| [EPIC-029C](incomplete/EPIC-029C_grid_planner.md) | The Grid planner: plan, derived values, verdicts, ATR and Bollinger | Elite | 029B | 🟢 | Planned |

**Critical path of the fast track:** 029B → 029C, then two branches that meet at 029H:

- 029A and 029C → 029E;
- 029C → 029G → 029F.

029D (after 029C and 029G) runs beside both branches. 029H needs 029D, 029E, 029F and 029G.

The same graph is drawn in `TRACKING.md`.

## 4. Phase exit criteria

| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| F0 — seams (029A, 029B) | A budgeted owner keeps 10 resting LIMIT orders on one symbol on the fake exchange. Bots persist and survive a restart. Every module guard passes. | Unit and integration tests; architecture guards; the red-then-green parser test for D8. Not run. |
| F1 — planner (029C) | The report's worked example reproduced as known answers, and every check's boundary tested | Unit tests and a mutation run. Not run. |
| F2 — live bot, tab, chart (029E, 029F, 029G) and backtest (029D) | A 6-level grid cycles, halts on an Emergency Stop and reconciles after a restart on the fake exchange. The tab drives it. One overlay draws three surfaces. The backtest states its fill rule. | Integration tests, `qtbot` tests, the preview, the sanity route scan. Not run. |
| F3 — Testnet (029H) | One Grid bot on Spot Testnet for 24 hours or more, through two restarts and an Emergency Stop. Its record is reconciled with the exchange and with the backtest of the same period. | The gated Testnet test run by the user, and the soak report. Not run. |
| After the fast track (029I–029L) | Desks manual only; many bots; Grid on Futures; signal and DCA kinds | Per task. Not run. |

## 5. Out of scope

- **Mainnet:** `EPIC-026`'s gates, plus a real-data backtest of the configuration (PRO-006 §2.1).
- **Exchange-side stop loss and OCO:** `EPIC-026K`.
- **Binance's hosted Grid product** (PRO-006 §2.3).
- **Improving the six signal strategies.**
- **More than one bot on one symbol.**

## Notes (newest first)

- **2026-10-03** — Review round 1 (PR #317, NEEDS_REVISION) addressed. The changes:
  - the owner book is derived from exchange evidence, never from the bot's store;
  - STOPPING ends only on zero tagged orders;
  - ERROR has an exit;
  - reconciliation checks holding ≥ inventory;
  - `max_notional_per_order` is kept and the opening buy is sliced (D21, O5);
  - seven citations are corrected;
  - the order-rate window, the level FSM file and a single dependency graph are added.

- **2026-10-03** — Epic scaffolded from the accepted `PRO-006`. The two code surveys behind the ADR
  found the session limits refusing a ladder's second order, and Emergency Stop selling a Spot
  bot's inventory. Both are designed for in D6 and D13.
