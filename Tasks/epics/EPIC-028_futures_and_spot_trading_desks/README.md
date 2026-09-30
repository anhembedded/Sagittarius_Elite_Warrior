# EPIC-028 — Two trading desks: Futures and Spot side by side, each with manual orders, a strategy and live account data

- **Status:** 🟡 Phase 2 in progress — ADR accepted 2026-09-29 (D1–D8, O1–O5 per recommendation); Phase 1 done (`EPIC-028A`–`028C`); `EPIC-028D` done; `EPIC-028E` in progress
- **Repositories:** Elite. No Engine change is expected.
- **Origin:** the user (2026-09-29): *"giờ màn hình trading đang có vấn đề, cần có 2 cái chứ không
  phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng, 2 màn hình
  đó phải có vào lệnh thủ công, và chọn strategy … khi kết nối tới binance thì phải get các data về
  thông tin tài khoản, vị thế"* ("there must be two trading screens, one Futures and one Spot; share
  what can be shared; both need manual orders and strategy selection; once connected they must
  fetch account information, positions, etc."), with four Binance screenshots as the reference.
- **North star:** [`Docs/HLD/11_desktop_workbench.md`](../../../Docs/HLD/11_desktop_workbench.md)
  (places, panels, dialogs) and [`Docs/HLD/04_surfaces_and_contribution_points.md`](../../../Docs/HLD/04_surfaces_and_contribution_points.md)
  (screen contributions). Both change in `EPIC-028M`.
- **Decisions:** [`DECISION_2026-09-29_two_trading_desks.md`](DECISION_2026-09-29_two_trading_desks.md)
  (D1–D8 and O1–O5 🟢 Accepted 2026-09-29).
- **Tracking (Gantt, PR matrix):** [`TRACKING.md`](TRACKING.md).
- **Dependencies:** builds on [`EPIC-027`](../EPIC-027_spot_trading_and_spot_backtest/README.md)
  (✅ Done — Spot adapters, holdings, Spot user data stream). Spot TP/SL waits on
  [`EPIC-026K`](../EPIC-026_road_to_real_money/README.md)'s protective orders (ADR O2).

---

## 1. Decisions already made
All eight accepted by the user on 2026-09-29, and O1–O5 answered with the recommendation (one process for both venues; Futures TP/SL now, Spot TP/SL with `EPIC-026K`; Stop-limit included; the old route retired; 7 days / 50 rows of history). The ones that shape the plan:
1. Two screens, two routes, each bound to one venue (D1).
2. Both venues live in one process through a per-venue `VenueContext` (D2) — the riskiest change.
3. Every venue-touching command and query names its venue (D3); config becomes a set (D4).
4. One shared desk kit; Futures/Spot differences in small variant classes behind a `DeskProfile` (D5).
5. New account read ports: summary, open orders, order history, trade history, commission (D6);
   leverage / margin mode as commands (D7); estimates as tested domain policies (D8).

## 1.1 What the tree already has (measured 2026-09-29, `faf4a337`)
| Capability | Where |
| :--- | :--- |
| Positions / Holdings / Open orders panels and table models | `trading/ui/order_book/` |
| One coordinator rendering them for both screens | `trading/ui/live_order_book_coordinator.py` |
| Strategy card + arming (both screens) | `ui/strategy_card_view_model.py`, `ui/strategy_arming_coordinator.py` |
| Manual order (Dev Board only): Market/Limit, qty, price | `dashboard/dev_board_widgets/manual_order_card.py` |
| Order path end to end | `OrderSubmissionService` → `ExecuteOrderCommand` → `ITradingClient` |
| Spot and Futures adapters (client, account reader, stream, metadata) | `trading/adapters/binance/`, `…/spot/` |
| Account status: wallet balance, holdings, equity, position mode | `ExchangeConnectionStatus` |

## 1.2 What the tree does not have
- A second screen, or any way to run Futures and Spot in one process.
- Manual order entry on the Trading screen; leverage / margin mode / TP-SL / reduce-only / TIF /
  stop-limit / % slider / total / fee estimate / max buy / liquidation estimate anywhere.
- Available balance, order history, trade history, commission rates — nothing reads them; the GUI
  shows no balance at all.

## 2. Goals — measurable
| Metric | Today (measured 2026-09-29) | When the epic is done |
| :--- | :-: | :-: |
| Trading screens (routes) | 1 (`trading`) | 2 (`trading.futures`, `trading.spot`) |
| Venues live at once in one process | 1 | 2 |
| Screens with manual order entry | 0 (Dev Board only) | 2 desks + Dev Board, one shared panel |
| Order types a desk can place | 2 (Market, Limit — Dev Board) | 3 (+ Stop-limit) and Futures TP/SL |
| Account figures shown in the GUI | 0 | available, wallet/margin, uPnL (Futures); free/locked, equity (Spot) |
| Bottom tabs with exchange data | 2 (positions/holdings, open orders via events) | 5 (+ order history, trade history, assets), loaded on open |
| Docstrings asserting "one venue per process" | 4 | 0 |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| **Phase 1 — Both venues in one process** | | | | | |
| [EPIC-028A](completed/EPIC-028A_venue_context_and_registry.md) | Per-venue `VenueContext` + `IVenueContexts` registry; config becomes a set | Elite | ADR O1 | 🔴 | ✅ Done (2026-09-29) |
| [EPIC-028B](completed/EPIC-028B_venue_addressed_commands.md) | Every venue-touching command/query names its venue; gates per venue | Elite | A | 🔴 | ✅ Done (2026-09-29) |
| [EPIC-028C](completed/EPIC-028C_both_venues_running_concurrently.md) | Both streams, refresh services and sessions run concurrently; Settings toggles | Elite | A, B | 🟡 | ✅ Done (2026-09-30) |
| **Phase 2 — Account data** | | | | | |
| [EPIC-028D](completed/EPIC-028D_account_summary_reader.md) | Account summary (available, wallet, margin, uPnL / free, locked, equity) | Elite | B | 🟡 | ✅ Done |
| [EPIC-028E](incomplete/EPIC-028E_open_orders_and_history_readers.md) | Open-orders query, order history, trade history | Elite | B, O5 | 🟡 | 🟡 In progress |
| [EPIC-028F](incomplete/EPIC-028F_commission_and_futures_account_controls.md) | Commission rates; change leverage / margin mode | Elite | B | 🟡 | Planned |
| [EPIC-028G](incomplete/EPIC-028G_order_estimate_policies.md) | Max quantity, cost, fee, liquidation estimate as domain policies | Elite | D, F | 🟢 | Planned |
| **Phase 3 — Shared desk kit** | | | | | |
| [EPIC-028H](incomplete/EPIC-028H_order_entry_panel_core_and_spot.md) | `DeskProfile` + order-entry panel core + Spot variant | Elite | G | 🟡 | Planned |
| [EPIC-028I](incomplete/EPIC-028I_futures_order_entry_variant.md) | Futures variant: margin/leverage chips, reduce-only, TIF, TP/SL, stop-limit | Elite | F, H, O2, O3 | 🔴 | Planned |
| [EPIC-028J](incomplete/EPIC-028J_account_tabs_and_summary_panels.md) | Bottom account tabs + account summary panel | Elite | D, E | 🟡 | Planned |
| **Phase 4 — Two desks** | | | | | |
| [EPIC-028K](incomplete/EPIC-028K_futures_desk_screen.md) | Futures desk screen | Elite | C, I, J | 🟡 | Planned |
| [EPIC-028L](incomplete/EPIC-028L_spot_desk_screen.md) | Spot desk screen | Elite | C, H, J | 🟢 | Planned |
| [EPIC-028M](incomplete/EPIC-028M_retire_single_trading_screen_and_docs.md) | Retire the single Trading route; Dev Board F9 on the shared panel; HLD/SPEC | Elite | K, L, O4 | 🟢 | Planned |
| [EPIC-028N](incomplete/EPIC-028N_dual_venue_testnet_tier.md) | Testnet tier: one round trip on each desk in the same process | Elite | K, L | 🟡 | Planned |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| Phase 1 | One process runs Futures and Spot at once; an order, cancel, Enable or Emergency Stop on one venue never touches the other. | Integration test against the fake exchange serving both `/fapi` and `/api` in one process; the four "one venue" docstrings rewritten; full gate green on GitHub Actions. Not run. |
| Phase 2 | Every account figure and history tab has a query that returns real exchange data for both venues. | Fake-exchange integration tests per reader; `exchange-status` CLI prints available balance. Not run. |
| Phase 3 | The desk kit places Market / Limit / Stop-limit on both venues and Futures TP/SL, with estimates shown. | Panel unit tests (`qtbot`), `preview.py` for every new package, estimate policies mutation-verified. Not run. |
| Phase 4 | Two desks in the nav, each with order entry, strategy card, account summary and tabs; the old route gone. | `tests/sanity` route scan shows two desks; the user's own Testnet run of `EPIC-028N` pasted into its task file. Not run. |

## 5. Out of scope
- **Mainnet** on either venue — `EPIC-026`'s gates.
- **Spot TP/SL (OCO)** — with `EPIC-026K` (ADR O2).
- **Cross Margin / Isolated margin Spot trading and Grid bots** (tabs in the Spot screenshot) — a
  third market with its own API (`EPIC-027` §5).
- **Iceberg, SOR/AOR, trailing-delta orders** (columns in the screenshot) — shown as "—".
- **Position history and balance-change history** (Futures tabs) — a follow-up once order/trade
  history exist.
- **Arming more than one strategy per desk.**

## Notes (newest first)
- **2026-09-30** — `EPIC-028E` implemented: one `IAccountHistoryReader` per venue (orders, fills, active symbols; ADR D6 amended), reads split to the exchange's span and row limits and never truncated; `GetOpenOrdersQuery`, `GetOrderHistoryQuery` and `GetTradeHistoryQuery` (fifty rows a page, newest first); the Spot average entry price rebuilt from fills, `None` whenever they do not explain the holding (closes `EPIC-027` ADR O6). Awaiting independent review.
- **2026-09-30** — `EPIC-028D` merged (PR #296) after an independent review (PASS, three should-fix items and two questions, all addressed before merge: a ticket fence drops a stale summary, SPEC-003 and ADR D6 updated, a lasting unreadable figure warns once per outage). `EPIC-028E` is next.
- **2026-09-30** — `EPIC-028D` implemented: `AccountSummary` (Futures: available, wallet, margin, uPnL, mode; Spot: quote free/locked, equity) carried on the connection check both readers already make, so no new port and no second request; `GetAccountSummaryQuery`; a per-venue refresh on the account cadence and after each fill of that venue, off the stream's loop; `exchange-status` prints the Futures available balance. Awaiting independent review.
- **2026-09-30** — `EPIC-028C` merged (PR #295) after an independent review (PASS, three should-fix items and one question, all addressed before merge). Phase 1 exit met: each venue's Emergency Stop, refresh, events, stream and saved strategy stay on that venue. `EPIC-028D` started.
- **2026-09-29** — `EPIC-028C` implemented in four slices: per-venue refresh and venue-stamped events, per-venue Settings toggles, one live stream per market with ticks routed by market, per-venue saved strategy. Awaiting independent review.
- **2026-09-29** — `EPIC-028B` merged (PR #294) after an independent review (PASS); its four should-fix items ride the `EPIC-028C` PR. `EPIC-028C` started.
- **2026-09-29** — `EPIC-028A` merged (PR #293) after an independent review; its four fixes are recorded in the task file.
- **2026-09-29** — `EPIC-028B` implemented: every venue-touching command and query names its venue, handlers resolve it once, the single-venue port bindings are gone and a guard keeps them gone. Tick routing by market and per-venue arming persistence moved to `EPIC-028C`. Awaiting independent review.
- **2026-09-29** — ADR accepted by the user ("đồng ý các khuyến nghị, bắt đầu làm 028A đi"); `EPIC-028A` started.
- **2026-09-29** — Epic scaffolded from a survey of the Trading screen, Dev Board, composition root
  and account ports on `faf4a337`; ADR proposed; 14 sub-tasks in four phases. Nothing accepted yet.
