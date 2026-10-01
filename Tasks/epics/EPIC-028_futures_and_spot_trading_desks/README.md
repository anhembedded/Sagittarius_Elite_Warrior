# EPIC-028 — Two trading desks: Futures and Spot side by side, each with manual orders, a strategy and live account data

- **Status:** 🟡 Phase 3 in progress — ADR accepted 2026-09-29 (D1–D8, O1–O5 per recommendation); Phase 1 done (`EPIC-028A`–`028C`, evidence `EPIC-028P`); Phase 2 readers done (`EPIC-028D`–`028G`, `028Q`), its exit check (the `exchange-status` CLI) not yet run; `EPIC-028H`, `028O`, `028R` and `028J` done; `028I` next
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
| [EPIC-028E](completed/EPIC-028E_open_orders_and_history_readers.md) | Open-orders query, order history, trade history | Elite | B, O5 | 🟡 | ✅ Done |
| [EPIC-028F](completed/EPIC-028F_commission_and_futures_account_controls.md) | Commission rates; change leverage / margin mode | Elite | B | 🟡 | ✅ Done |
| [EPIC-028G](completed/EPIC-028G_order_estimate_policies.md) | Max quantity, cost, fee, liquidation estimate as domain policies | Elite | D, F | 🟢 | ✅ Done (2026-10-01) |
| **Phase 3 — Shared desk kit** | | | | | |
| [EPIC-028H](completed/EPIC-028H_order_entry_panel_core_and_spot.md) | `DeskProfile` + order-entry panel core + Spot variant | Elite | G | 🟡 | ✅ Done (2026-10-01) |
| [EPIC-028O](completed/EPIC-028O_order_contract_and_missing_reads.md) | Order contract end to end (stop price, TIF, quote quantity, stop-limit on both venues); reads for leverage, brackets, mark, best bid/ask, the app's notional limit | Elite | H, O3 | 🔴 | ✅ Done (2026-10-01) |
| [EPIC-028P](completed/EPIC-028P_dual_venue_isolation_test.md) | Phase 1 evidence: both venues in one process against one fake exchange | Elite | C | 🟢 | ✅ Done (2026-10-01) |
| [EPIC-028Q](completed/EPIC-028Q_phase_2_reader_fixes.md) | Phase 2 reader fixes: history gaps disclosed, closed trades found, errors translated, stale balance marked | Elite | E, F | 🟡 | ✅ Done (2026-10-01) |
| [EPIC-028R](completed/EPIC-028R_futures_conditional_orders_via_algo_api.md) | Futures conditional orders through Binance's Algo Order API: sent with the app's client id, listed, cancelled, cancelled by Emergency Stop | Elite | O | 🔴 | ✅ Done (2026-10-01) |
| [EPIC-028I](incomplete/EPIC-028I_futures_order_entry_variant.md) | Futures variant: margin/leverage chips, reduce-only, TIF, TP/SL, stop-limit tab | Elite | F, H, O, R, O2 | 🔴 | Planned |
| [EPIC-028J](completed/EPIC-028J_account_tabs_and_summary_panels.md) | Bottom account tabs + account summary panel | Elite | D, E | 🟡 | ✅ Done (2026-10-01) |
| **Phase 4 — Two desks** | | | | | |
| [EPIC-028K](incomplete/EPIC-028K_futures_desk_screen.md) | Futures desk screen | Elite | C, I, J | 🟡 | Planned |
| [EPIC-028L](incomplete/EPIC-028L_spot_desk_screen.md) | Spot desk screen | Elite | C, H, J, O | 🟢 | Planned |
| [EPIC-028M](incomplete/EPIC-028M_retire_single_trading_screen_and_docs.md) | Retire the single Trading route; Dev Board F9 on the shared panel; HLD/SPEC | Elite | K, L, O4 | 🟢 | Planned |
| [EPIC-028N](incomplete/EPIC-028N_dual_venue_testnet_tier.md) | Testnet tier: one round trip on each desk in the same process | Elite | K, L | 🟡 | Planned |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| Phase 1 | One process runs Futures and Spot at once; an order, cancel, Enable or Emergency Stop on one venue never touches the other. | Integration test against the fake exchange serving both `/fapi` and `/api` in one process (`EPIC-028P`: `test_two_venues_in_one_process_against_fake_server.py`); the four "one venue" docstrings rewritten; full gate green on GitHub Actions. The integration test was missing when Phase 1 was recorded as met (the PR #300 epic review); when added, it found Futures sessions pinging the Spot API, fixed in the same change. |
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
- **2026-10-01** — `EPIC-028J` done: each desk's account tabs (open orders, order and trade history, positions or assets) load from the venue when the desk opens and keep current from its events; cancel all and close at market ask first; the histories name the pairs they read and page over a fixed span. The summary panel marks stale figures with the reason. Built as parts; `EPIC-028K`/`028L` put them on the desks.
- **2026-10-01** — `EPIC-028O` merged (PR #305). `EPIC-028R` done: a Futures stop-limit goes through Binance's Algo Order API under the app's client order id, and conditional orders are listed, cancelled, kept in history and cancelled by Emergency Stop wherever they were placed. A triggered stop's fill reaches the app as the order it placed. No live Testnet call verified the algo shapes (`EPIC-028N`).
- **2026-10-01** — `EPIC-028O` done: PR-1 to PR-3 merged (#302, #303, #304), and PR-4 adds the desk UI: the Spot Stop-limit tab, the quote-sized market buy, the BBO button, and every maximum capped by the app's per-order notional limit. The Futures half of stop-limit waits on `028R` (sending) and `028I` (the Futures profile).
- **2026-10-01** — `EPIC-028H`, `028P` and `028Q` merged (PR #301) after an independent review (PASS; two should-fix items fixed before merge: the cache's `since` guard on trades had no test, and the Active symbols vocabulary row was stale). Phase 1's exit now has its integration evidence. Phase 2's readers are done; its exit row still asks for the `exchange-status` CLI check. `EPIC-028O` is next.
- **2026-10-01** — `EPIC-028G` merged (PR #300) after two independent reviews (the second PASS). The epic-level review on the same PR re-planned the epic: `EPIC-028O` widened, `EPIC-028P` and `EPIC-028Q` added.
- **2026-09-30** — `EPIC-028G` implemented, then redesigned after the first independent review (PR #300) showed the first version's "errs low, never high" claim false for Futures. The shared fee and step fitting stay common. Futures cost and maximum now follow Binance's rules: assuming price, open loss and the bracket's notional headroom. A limit order at the maximum is never refused for margin or notional, while a market order's open loss against the book is not modelled. Spot is sized by notional plus fee. The liquidation estimate uses Binance's one-way formula, exact for isolated margin and optimistic for cross. 43 targeted mutations, all killed. The re-review passed.
- **2026-09-30** — `EPIC-028F` merged (PR #299) after two independent reviews. The first review (NEEDS_REVISION) found the gate's open-position read outside the port's error translation: a network drop leaked as `requests.ConnectionError`. The read moved onto the port (`IFuturesAccountControl.open_position`), every answer is now read inside the translation, and a symbol a strategy manages is refused. The re-review passed. `EPIC-028G` is next.
- **2026-09-30** — `EPIC-028F` implemented. Two narrow ports, `IFuturesAccountControl` (Spot's `VenueContext` holds `None`) and `ICommissionRateReader`. `ChangeLeverageCommand` and `ChangeMarginTypeCommand` pass one gate: a disabled venue, Spot or the switch off is refused with no request, then the connection is checked and an open position is refused before anything is sent. `GetCommissionRateQuery` answers per venue. Fast tier green; awaiting independent review.
- **2026-09-30** — `EPIC-028E` merged (PR #297) after two independent reviews. The first found one blocking defect: Spot active symbols downloaded the whole `exchangeInfo` catalog once per unlisted asset, and a failed download leaked the SDK error. `ListedSymbols` fixed it with one refresh, a memo of unlisted pairs and failure translation. The same round added a 30-day `MAX_HISTORY_LOOKBACK`. The re-review passed; its follow-ups made the verified fake enforce the lookback through the contract and put the aggregate request-weight cost on `EPIC-028J`. `EPIC-028F` is next.
- **2026-09-30** — `EPIC-028E` implemented: one `IAccountHistoryReader` per venue (orders, fills, active symbols; ADR D6 amended), reads split to the exchange's span and row limits and never truncated; `GetOpenOrdersQuery`, `GetOrderHistoryQuery` and `GetTradeHistoryQuery` (fifty rows a page, newest first); the Spot average entry price rebuilt from fills, `None` whenever they do not explain the holding (closes `EPIC-027` ADR O6). Awaiting independent review.
- **2026-09-30** — `EPIC-028D` merged (PR #296) after an independent review (PASS, three should-fix items and two questions, all addressed before merge: a ticket fence drops a stale summary, SPEC-003 and ADR D6 updated, a lasting unreadable figure warns once per outage). `EPIC-028E` is next.
- **2026-09-30** — `EPIC-028D` implemented: `AccountSummary` (Futures: available, wallet, margin, uPnL, mode; Spot: quote free/locked, equity) carried on the connection check both readers already make, so no new port and no second request; `GetAccountSummaryQuery`; a per-venue refresh on the account cadence and after each fill of that venue, off the stream's loop; `exchange-status` prints the Futures available balance. Awaiting independent review.
- **2026-09-30** — `EPIC-028C` merged (PR #295) after an independent review (PASS, three should-fix items and one question, all addressed before merge). Phase 1 exit recorded as met (correction, 2026-10-01: the integration-test evidence the exit row requires was missing; `EPIC-028P` supplies it): each venue's Emergency Stop, refresh, events, stream and saved strategy stay on that venue. `EPIC-028D` started.
- **2026-09-29** — `EPIC-028C` implemented in four slices: per-venue refresh and venue-stamped events, per-venue Settings toggles, one live stream per market with ticks routed by market, per-venue saved strategy. Awaiting independent review.
- **2026-09-29** — `EPIC-028B` merged (PR #294) after an independent review (PASS); its four should-fix items ride the `EPIC-028C` PR. `EPIC-028C` started.
- **2026-09-29** — `EPIC-028A` merged (PR #293) after an independent review; its four fixes are recorded in the task file.
- **2026-09-29** — `EPIC-028B` implemented: every venue-touching command and query names its venue, handlers resolve it once, the single-venue port bindings are gone and a guard keeps them gone. Tick routing by market and per-venue arming persistence moved to `EPIC-028C`. Awaiting independent review.
- **2026-09-29** — ADR accepted by the user ("đồng ý các khuyến nghị, bắt đầu làm 028A đi"); `EPIC-028A` started.
- **2026-09-29** — Epic scaffolded from a survey of the Trading screen, Dev Board, composition root
  and account ports on `faf4a337`; ADR proposed; 14 sub-tasks in four phases. Nothing accepted yet.
