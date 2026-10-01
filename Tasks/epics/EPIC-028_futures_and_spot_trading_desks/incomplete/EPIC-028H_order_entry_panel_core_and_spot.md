# EPIC-028H — One order-entry panel places Limit and Market orders; the Spot variant shows Buy and Sell side by side

**Status:** 🟡 Implemented — awaiting review
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — the panel places real orders; its dispatch must stay the one `IOrderSubmission` path
**Complexity:** L — new shared UI package, view model, presenter, Spot variant, preview
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028G](../completed/EPIC-028G_order_estimate_policies.md)

---

## 1. Context and problem
- `dev_board_widgets/manual_order_card.py` (170 lines) has a Market/Limit combo, a quantity, a price and two buttons. It has no total, no slider, no TP/SL and no estimates. HLD 11 §11.3 plans panels under `trading/ui/panels/`.
- Nothing in the app reads a symbol's filters or the account's fee for the UI. The order path rounds at submit time, and `GetCommissionRateQuery` (`EPIC-028F`) had no consumer.

## 2. Acceptance criteria
- [x] A `DeskProfile` selects the variant: market type, side labels, order types, layout, how each side's figures are computed, and whether TP/SL is available. No widget branches on `is_spot`.
- [x] Core panel:
  - tabs for the order types the profile offers (Limit, Market);
  - a price field with a "Last" fill;
  - an amount field;
  - a 0–100 % slider bound to the maximum;
  - the total in quote and the estimated fee;
  - a TP/SL toggle, shown but disabled on Spot with its reason (ADR O2).
- [x] Spot variant: two columns, Buy and Sell, each showing the available balance and max buy or max sell. Sell is disabled without a holding (the `EPIC-027O` rule is kept).
- [x] Submitting goes preview → confirm → submit through the panel's own venue's `IOrderSubmission`. The quantity and price sent are the preview's, rounded to the symbol's filters. A money-moving submit confirms in a dialog that names the rounded order, its total and its fee (HLD 11 §11.5).
- [x] `preview.py` renders the Spot variant.
- **Moved to [`EPIC-028O`](EPIC-028O_order_contract_and_missing_reads.md):**
  - the Stop-limit tab: the submission path cannot send a stop-limit order yet, and drawing the tab would offer something it refuses;
  - the BBO price fill: nothing reads the order book.

  The Futures variant (`EPIC-028I`) shares no widget with this task beyond the core.

## 3. Design (as built)
- **MVP, one package** (`trading/ui/desk/order_entry/`), per `ui-presentation-rule.md` §3:
  - `order_entry_view_model.py`: plain state behind one `changed` signal. Typed text is kept parsed, and an unreadable field is `None`, never zero.
  - `order_entry_presenter.py`: reads, preview → confirm → submit.
  - `order_entry_panel.py`: the tabs, the TP/SL toggle, the sides and a status line.
  - `order_side_form.py`: one side's fields and figures.
  - `two_column_sides.py`: the Spot layout.
- **The numbers are Qt-free** (`order_entry_rules.py`). `spot_side_figures` answers what a side shows and the first problem that stops it, in the order a user fixes them: nothing to sell, no price, no amount, below one lot, below the minimum notional, balance unknown, over the maximum.
  - The maximum is `EPIC-028G`'s `spot_max_buy_quantity`, or the free base floored to the step.
  - A market order is sized at the last price, with `MARKET_LOT_SIZE`'s step.
- **Variants by data, not branches (ADR D5).** `DeskProfile` carries the order types, labels, layout, the figures rule and the TP/SL reason. The panel picks the layout from `_SIDE_LAYOUTS`. A new desk adds one profile builder, one layout entry and one figures function, and touches no widget.
- **One new published read, `IOrderEntryTerms`** (a `VenueTradingPorts` field), answers a symbol's filters (`GetSymbolOrderRulesQuery`, from the venue's metadata provider, the same one preview rounds with) and the account's fee (`GetCommissionRateQuery`). The balances come from `IAccountSnapshot.check_connection()` (`summary`, `holdings`). A summary on an unreachable status is not trusted.
- **Submit.**
  1. **Preview** on a worker: the exchange-rounded order, refused if it is empty or below the minimum notional.
  2. **Confirm** on the UI thread, through an injected `ConfirmOrder`; Cancel sends nothing.
  3. **Submit** on a worker: the position and the Spot holding are read fresh, and `manual_order_intent_for()` gives the side and `reduce_only`, the same rule the Dev Board card uses. Then `submit(live=True)` runs every gate and limit.
- **Fencing.** Loads and orders each carry an action id from an `ActionOwnershipTracker`. A superseded answer is logged and dropped, and a second submit while one is out is refused.
- **Not a desk yet.** Nothing hosts the panel: the Spot desk (`EPIC-028L`) will, and it will feed the last price and call `refresh()` after fills.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_order_entry_terms.py`, `order_entry_terms.py`, `symbol_rules_unavailable_error.py` | new: the published read and its answer |
| `src/modules/trading/contracts/venue_trading_ports.py` | `order_entry_terms` field |
| `src/modules/trading/application/queries/get_symbol_order_rules/` | new query and handler |
| `src/modules/trading/application/orders/order_entry_terms_service.py` | new: `IOrderEntryTerms` over the two queries |
| `src/modules/trading/composition/query_bindings.py`, `venue_trading_ports_registry.py` | bind the query; build the service per venue |
| `src/modules/trading/contracts/testing/fake_order_entry_terms.py`, `fake_venue_trading_ports.py` | the verified fake |
| `src/modules/trading/ui/desk/desk_profile.py` | new |
| `src/modules/trading/ui/desk/order_entry/` | new package: rules, view model, presenter, confirmation, panel, side form, two-column layout, amount text, preview |

## 5. Testing
- **Rules** (`test_order_entry_rules.py`):
  - each problem, in order;
  - limit vs market price and step;
  - the maximum fits and one more step does not;
  - the slider helpers.
- **View model:** parsing, per-side inputs, the slider on the step, a new symbol forgets the old one, no-op edits are silent.
- **Presenter**, with verified fakes and inline or held workers:
  - the load reads terms and balances; an unreachable account leaves them unknown; an unknown symbol is reported;
  - a superseded load is dropped, and another venue's ports are refused;
  - a confirmed Buy is sent rounded as previewed, and live;
  - a market order is priced at the last price;
  - a Sell whose holding vanished before submit is refused by the fresh read;
  - Cancel sends nothing; a side with a problem is not previewed; a preview below the minimum is not confirmed;
  - a blocked result names the gate; a second submit is refused.
- **Panel (qtbot):** the tabs, typing, the slider, Sell disabled without a holding, nothing live before the terms arrive, the busy lock, and TP/SL disabled with its reason.
- **Application:** the rules query answers per venue and refuses an unknown symbol; the service addresses its own venue; the registry binds it per venue.
- **Integration** (`test_spot_order_panel_against_fake_server.py`): a confirmed market Buy on the panel, through the real handlers, `SpotTradingClient` and the fake exchange, raises the BTC holding and lowers the spendable USDT.
- **Mutation check:** 28 targeted mutations; 27 were killed. The survivor, submitting the previewed request without the intent's side and `reduce_only`, is equivalent on Spot, where both always equal the request's. The Futures variant (`EPIC-028I`) is where a test can tell them apart.

## Implementation notes
- **Two AC items moved to `EPIC-028O`**, and ADR O3 still stands (stop-limit on both desks):
  - A stop-limit order needs a stop price on `OrderRequest`, a new `OrderType`, both venues' payload mappers and the fake exchange. That is order-path work, and keeping it out of a UI diff keeps a money-moving change reviewable on its own.
  - The BBO fill needs a book read.
- **"Last" instead of "BBO".** The price button fills the last traded price, which the desk already streams. It is named for what it is.
- **The Dev Board card is untouched.** `EPIC-028M` rebuilds the F9 dialog on this panel.
