# EPIC-028J — Each desk has an account summary and bottom tabs: open orders, order history, trade history, positions or assets

**Status:** ✅ Done (2026-10-01)
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — reuses the existing tables; the change is loading them from queries, not only events
**Complexity:** M — two panels, reuse `ui/order_book/`
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028D](../completed/EPIC-028D_account_summary_reader.md), [EPIC-028E](../completed/EPIC-028E_open_orders_and_history_readers.md)

---

## 1. Context and problem
- `ui/order_book/` has Positions, Holdings and Open-orders panels; no history tables; no summary.

## 2. Acceptance criteria
- [x] Tabs: Open orders (cancel one, cancel all — confirmed), Order history, Trade history, and Positions (Futures, with close-at-market) or Assets (Spot).
- [x] Every tab loads from its query when the desk opens and updates from events of its own venue.
- [x] A "hide other pairs" toggle filters to the desk's symbol.
- [x] With "hide other pairs" off, the Order history and Trade history tabs name the pairs they show (`HistoryPage.scanned_symbols`, `EPIC-028E`): Binance needs a symbol per history request, so "every pair" is the venue's active symbols, and a pair closed out with nothing open is not among them. The tab never implies the list is the whole account (PR #297 review, finding 3).
- [x] Reading every pair stays inside Binance's request-weight limit (6 000 a minute): `IAccountHistoryReader`'s thirty-day bound is per symbol and endpoint, a Spot page of every pair re-reads the span for each active symbol (31 requests × weight 20 per symbol at thirty days, 8 at ADR O5's seven), and each page request reads again. The tabs cache a span behind the port (its listed caching decorator) or cap the pairs scanned with `symbol=None`, and a test shows flipping pages does not re-read the exchange (PR #297 re-review, finding 2). *Built by [EPIC-028Q](../completed/EPIC-028Q_phase_2_reader_fixes.md): `CachedAccountHistoryReader` wraps both venues' readers; the tabs only need to keep `since` fixed while paging.*
- [x] The summary panel shows the `EPIC-028D` figures and refreshes on fills.
- [x] Each history tab shows its page's `HistoryPage.notices` (what the venue cannot return, `EPIC-028Q`) near the rows, not in a tooltip.
- [x] The summary panel marks its figures stale on `AccountSummaryStaleEvent` of its venue, with the event's reason, and clears the mark on the next `AccountSummaryChangedEvent` (`EPIC-028Q`).

## 3. Design
- **A venue-bound read port.** `IAccountActivity` (summary, every open order, one history page) joins `VenueTradingPorts` as `account_activity`. `AccountActivityService` is a façade over the existing venue-addressed queries, like `OrderEntryTermsService`. Positions and holdings stay `IAccountSnapshot`'s.
- **`AccountTabsPanel`** (`QTabWidget`) composes the existing `OpenOrdersPanel`, `PositionsPanel`/`HoldingsPanel` and two `HistoryPanel`s. `DeskProfile.held_tab` picks Positions or Assets. It implements `OrderBookDisplay`, so `LiveOrderBookCoordinator` drives it unchanged.
- **Loaded from queries, kept by events.** `AccountTabsPresenter` reads the account when the desk opens and hands the snapshot to the coordinator's full reconciliation. The venue's `OrderFeed` keeps it current from then on.
- **Histories** (`HistoryTabsLoader`): `since` is set when a history opens (desk opened, symbol changed, "hide other pairs" flipped) and kept while paging, so `CachedAccountHistoryReader` answers page clicks from its cache. A fill re-reads the pages shown.
- **Actions** (`AccountTabActions`): cancel one, cancel all shown (one cancel per order, stopping at a safety-gate refusal), close at market (`market_close_order_for`: the position read again, reduce-only, opposite side, whole size). All go through `IOrderSubmission`, so every gate applies.
- **Summary** (`AccountSummaryPanel`, `AccountSummaryPresenter`): read once on open, then `AccountSummaryChangedEvent`/`AccountSummaryStaleEvent` through `OrderFeed` (two new signals, venue-filtered).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_account_activity.py`, `history_request.py` | new port and its page request |
| `src/modules/trading/contracts/venue_trading_ports.py`, `composition/venue_trading_ports_registry.py` | `account_activity` field and its one line |
| `src/modules/trading/application/account/account_activity_service.py` | new façade |
| `src/modules/trading/contracts/testing/fake_account_activity.py`, `fake_venue_trading_ports.py` | verified fake, default in `fake_venue_ports` |
| `src/modules/trading/domain/policies/position_close_order.py` | the close-at-market order |
| `src/modules/trading/ui/desk/account_tabs/` | panel, presenter, history loader, actions, rows, models, confirmations, preview |
| `src/modules/trading/ui/desk/account_summary/` | panel, presenter, lines, preview |
| `src/modules/trading/ui/order_feed.py` | `accountSummaryChanged`, `accountSummaryStale` |
| `src/modules/trading/ui/order_book/open_orders_panel.py`, `positions_panel.py` | `add_action()`; positions `selected_row()` and `selectionChanged` |
| `src/modules/trading/ui/desk/desk_profile.py` | `HeldTab`, `held_tab` |

## 5. Testing
- Unit: `test_account_activity_service.py`, `test_account_activity_fake.py`, `test_position_close_order.py`, `test_history_view.py`, `test_account_tabs_panel.py` (qtbot, real clicks), `test_account_tabs_presenter.py`, `test_account_summary.py`, `test_order_feed.py` (summary events filtered by venue).
- Integration: `test_account_tabs_against_fake_server.py`. A resting limit and a conditional order are placed straight on the fake exchange; a Futures desk opened afterwards lists both, shows them in its order history, and "Cancel all" cancels both through the real handlers (regular and algo `DELETE`s on the wire).
- Mutation-checked: the pair filter, `since` kept while paging, the close side, the stop at a gate refusal, the hide-other-pairs symbol, the summary read fenced by a newer event, the feed's venue filter. Each mutation turned a test red.

## Implementation notes (written when done)
- **Not wired into a screen yet.** The tabs and the summary are built and tested as parts; `EPIC-028K`/`028L` put them on the two desks, as `EPIC-028H`'s order panel waits for them too.
- **Cancel all is one cancel per order shown**, not Binance's cancel-all endpoint. It cancels what the user saw and confirmed, across the pairs shown, and names each refusal. Emergency Stop keeps the venue-wide endpoints.
- **The summary refreshes on fills through `AccountSummaryRefreshService`** (`EPIC-028D`), which re-reads the account after each fill and publishes the change; the panel shows what it publishes.
- **Hide other pairs does not filter Assets.** A holding is not a pair, as on Binance's own Spot desk.
- **A fill re-reads the history pages shown** with the same `since`. The history cache makes a new fill appear up to its TTL (15 s) late.
- **Request weight** stays inside the limit through `EPIC-028Q`'s cache. `test_paging_keeps_the_span_the_history_opened_with` shows a page click reuses the span.
