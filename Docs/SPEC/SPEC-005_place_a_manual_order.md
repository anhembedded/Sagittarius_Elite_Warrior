# SPEC-005 — Place one order by hand

- **Status:** ✅ built and proven
- **Actor:** trader
- **Origin:** `EPIC-021F` (preview and dry run), `EPIC-021G` (live submission and the safety
  pipeline), `EPIC-024B` (the Dev Board panel), with `BUG-090` (the exchange's own minimum
  notional was never wired into the live path).
- **Surfaces:** the Dev Board's order dialog, opened with `F9` or from the header (a panel in
  the controls column until `EPIC-025` PR 1.4c-3 made it a dialog — order entry is occasional,
  and a form that sits in the layout is permanently in the way of what is not) ·
  `order-preview` · `order-dry-run` · `trade-once --live` at the command line and the
  interactive prompt.

## 1. Trigger

*"I want to send this one order myself, and I want to see exactly what will be sent before it
goes."*

## 2. Preconditions

1. Live trading is on (SPEC-004) — for a **live** submission only. Preview and dry run work with
   it off, which is the point of having them.
2. Credentials resolve and the venue is Futures Testnet.
3. The actor has a symbol, a side, a quantity and a reference price. The reference price is
   required, not optional: this app has no live mark-price path for the notional estimate, and
   the command line says so in its own help text rather than quietly using a stale number.

## 3. Main flow

1. The actor opens the order dialog — `F9`, or the header's *Place order* button — and names
   the symbol, the side, the quantity, the order type and the reference price. The dialog is
   modeless: the charts behind it keep ticking while the actor decides.
2. The app fetches that symbol's exchange filters and **normalises** the order: the quantity is
   rounded to the venue's step size, the price to its tick size.
3. The app computes the notional from the normalised quantity and the reference price, and
   checks it against the venue's own minimum. Below it, the order is refused **here** — before
   any network round trip — rather than being sent to collect a `-4164` rejection (`BUG-090`).
4. The app shows the actor the normalised order: what will actually be sent, not what they
   typed. On the command line this is `order-preview`, optionally as JSON.
5. To go further without sending anything, the actor runs `order-dry-run`: the app sends the
   normalised order to the exchange's **test** endpoint, which validates the signature,
   permissions and payload and creates nothing.
6. To submit, the actor asks for a live order — the dialog's Long or Short, or
   `trade-once --live`. The
   app then runs, in order and under one guard held across the whole decision:
   1. **three safety gates** — the venue is enabled, the trading switch is on, the connection is
      ready;
   2. the minimum-notional check from step 3;
   3. **four session limits** — orders per session, notional per order, positions per symbol,
      and the minimum interval between orders.
7. If nothing blocked it, the app submits one order, records it against the session's counters,
   and marks the symbol as believed-open.
8. The app answers once, with what blocked it or with the order that was sent.

## 4. What must be true afterwards

- What was sent is what step 4 showed. The actor never has to infer the normalisation.
- `live=False` is the default everywhere, and it is a **real** dry run: every gate and limit is
  evaluated against live data, and no order-submission network call is made at all.
- A refusal is a **named value on the result**, never an exception the caller had to anticipate:
  one of four safety gates, the notional rejection, or one of four limit violations.
- The result carries evaluation as far as it got, and the shape says which: a safety-gate block
  has no preview and no limit checks; a minimum-notional block has a preview and no limit
  checks; a limit block shows every check with the numbers it was judged against.
- The session's order counter went up by exactly one for one submitted order, and the symbol it
  names is marked believed-open immediately — before any fill confirmation.
- An exchange refusal arrives as a named reason with Binance's own text kept alongside it:
  insufficient margin, lot size, minimum notional, price filter, reduce-only rejected, rate
  limit, or `UNKNOWN`. No layer above Infrastructure ever sees a Binance error code.

## 5. When it goes wrong

| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| Trading is off, or the venue is disabled, or the connection is not ready | Blocked by the named safety gate; nothing was normalised and no limits were evaluated | The gates are cheap and come first, and the empty preview is how the actor knows evaluation stopped there |
| A strategy is armed on this symbol | Blocked by `SYMBOL_LEASED`, in the operator's own words: the strategy would lose track of its real position, so disarm it or trade a different symbol | The user's decision of 2026-09-09 (`PRO-003` §4.1.2), and it is *hard*, not a warning — even while the position is flat, because the strategy's next signal assumes it started flat. Enforced on the order path since `EPIC-025` PR 2.1f, so `trade-once` and every future caller inherit it; before that only the Dev Board's own form had it |
| The order is below the venue's minimum notional | Blocked by `MIN_NOTIONAL`, with the preview that shows the computed notional | `BUG-090`: refusing locally beats a round trip for a rejection the app could already predict |
| A session limit is reached | Blocked by that limit, with every check and the numbers behind it — e.g. order 21 of a 20-order session | The app's own configured safety policy, distinct from the venue's hard filters |
| The exchange refuses the submitted order | The named `OrderRejectionReason`, with the exchange's original message kept for a human to look up | A raw English exchange string is not a stable contract; the name is what a caller branches on |
| The actor submits twice quickly | The minimum-interval limit blocks the second one | One of the four limits, and the reason it exists |
| The network fails mid-submission | The failure reaches the actor, and the session's order counter does not move | The order is recorded against the session *after* the exchange call returns, so a submission that never landed cannot consume the session's budget |

## 6. What this use case does NOT promise

- **It does not follow the order to a fill.** The result answers once, for one submission.
  Watching an order fill over time is the user-data stream's `OrderFilledEvent`, and a caller
  that needs both has to correlate them by client order id. `IOrderSubmission`'s docstring
  records this as the one thing that is not a local change.
- It does not promise the fill price. A market order's notional is an estimate from the
  reference price the actor supplied.
- No brackets, no OCO, no take-profit pairing. One order, one answer.
- It does not reserve the symbol **for itself**. A manual order takes no lease and gives no
  protection from the next one; what changed in `EPIC-025` PR 2.1f is the other direction — a
  symbol an armed *strategy* claimed refuses a manual order (§5). Two manual orders on one symbol
  are still governed only by the session's limits.
- `trade-once` is not a daemon. It runs one strategy evaluation, attempts at most one order, and
  exits.

## 7. Ports and modules it exercises

`trading`: `IOrderSubmission` — `preview()`, `validate()`, `submit(live=…)`, `cancel()`, the only
way an order reaches the venue — with `OrderPreview`, `ExecuteOrderResult`,
`ExecuteOrderSafetyGate`, `TradingLimitViolation`, `OrderRejectionReason`,
`InvalidOrderForSubmissionError`, `ClientOrderId` and — since `EPIC-025` PR 2.1a — `OrderIntent`
as the published vocabulary. The four methods
are the four things step 3–6 do, and they are genuinely four: `preview()` makes no network call,
`validate()` reaches the venue's test endpoint and creates nothing, `submit(live=False)` evaluates
every gate against live data and sends nothing, `submit(live=True)` sends.
`OrderIntent` is what step 6's Long or Short resolves to before any of that runs: the
`(side, reduce_only)` pair, which is the whole of what One-way mode lets a caller decide. It is
published rather than internal because the Dev Board reads the pair `manual_order_intent_for()`
returns — *Long* against a short position and *Short* against a long one come back
`reduce_only=True`, and that flag is the difference between closing a position and opening the
opposite one.
`ITradingSession` holds the switch and the counters; `IMarketMetadataProvider` supplies the
filters step 2 rounds with; `ITradingClient` is the module's own adapter boundary. Cancelling one
open order is SPEC-006 (planned) and is the same port's `cancel()`.

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| Normalisation, the notional check, and the preview's shape | `tests/unit/modules/trading/application/orders/test_preview_order.py` | unit |
| Four gates, four limits, their order, and each result shape | `tests/unit/modules/trading/application/orders/test_execute_order.py` | unit |
| A leased symbol is refused, its holder is not, and the refusal costs no network call | `tests/unit/modules/trading/application/orders/test_execute_order.py` (`TestSafetyGates`) | unit |
| Arming claims the symbol and disarming gives it back — including a refused arming keeping nothing | `tests/unit/modules/strategy/application/use_cases/test_arm_strategy.py` | unit |
| Both implementations of `ITradingSession` hold the lease the same way | `tests/unit/modules/trading/contracts/test_trading_session_contract.py` + its integration twin | contract |
| A refused or undelivered submission never advances the session counters | `tests/unit/modules/trading/application/orders/test_execute_order.py` (`TestAFailedSubmissionIsNeverRecordedAsSent`) | unit |
| The four limits themselves, at the domain level | `tests/unit/modules/trading/domain/policies/test_trading_limit_policy.py` | unit |
| What a manual order is allowed to be, as a domain rule | `tests/unit/modules/trading/domain/policies/test_manual_order_intent.py` | unit |
| Both implementations of the port answer the same way | `tests/unit/modules/trading/contracts/test_order_submission_contract.py` | contract |
| The command line's preview report, text and JSON | `tests/unit/presentation/cli/test_order_preview_formatter.py` | unit |
| `order-preview` reaches the venue by neither route, and `order-dry-run` validates the order it previewed and submits nothing | `tests/unit/presentation/cli/test_order_cmds.py` | unit |
| Preview → dry run → submit against a fake Binance server | `tests/integration/application/test_manual_order_pipeline_against_fake_server.py` | integration |
| The Dev Board's order form, driven by real Qt clicks | `tests/integration/presentation/ui/test_dev_board_manual_order_qt_click.py` | integration |
| The form is a dialog `F9` opens, not a panel in the layout | `tests/unit/presentation/ui/screens/test_dashboard_view.py` | unit |
| One order's real life cycle on the real Futures Testnet | `tests/testnet/test_order_lifecycle.py` — **the user runs it**: `SEW_TESTNET_TESTS=1` plus real credentials, via `ci-local.ps1 -TestnetOnly`; the ordinary gate never invokes this tier | human |
| Submitting one order by hand | **the user runs it**: enable trading, press `F9` on the Dev Board, submit a small order, and confirm it appears in the Testnet web UI with the quantity the preview showed | human |
