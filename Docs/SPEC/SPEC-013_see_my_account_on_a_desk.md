# SPEC-013 — See my account on a desk

- **Status:** ✅ built and proven (the live-venue step is the user's, §8)
- **Actor:** trader
- **Origin:** the user, 2026-09-29 — two trading screens, one Futures and one Spot, and *"khi
  kết nối tới binance thì phải get các data về thông tin tài khoản, vị thế"* ("once connected to
  Binance, read the account information and the positions"). Built as `EPIC-028D`/`028E`/`028J`/
  `028K`/`028L`/`028M`; the [ADR](../../Tasks/epics/EPIC-028_futures_and_spot_trading_desks/DECISION_2026-09-29_two_trading_desks.md).
- **Surfaces:** the Futures desk (`trading.futures`, nav "Futures") and the Spot desk
  (`trading.spot`, nav "Spot"). The first run opens on the Futures desk, the default mode.

## 1. Trigger

*"I want to see what my Futures (or Spot) account holds right now: the money, what is open, what
I did, and how the account is doing."*

## 2. Preconditions

- The desk's venue is enabled in Settings (Futures Testnet or Spot Testnet) and the app was
  restarted after the change; `secrets.local.json` holds that venue's key pair.
- For figures to be current, the venue's user-data stream runs (started at boot for every enabled
  venue, `EPIC-028C`).

## 3. Main flow

1. The trader opens a desk.
2. The app reads that venue's account once: the summary panel and the account tabs fill. Nothing
   is read for the other venue, and opening a desk with trading off opens no market stream
   (`BUG-107`).
3. The summary shows the venue's own figures. Futures: available balance, wallet balance, margin
   balance and unrealised PnL, in USDT (or USD, said so, on a Multi-Assets account), and the
   position mode. Spot: the quote asset free and locked, and the account's value when it is known.
4. The tabs show the account: **Open orders** (with cancel one and cancel all), **Order history**
   and **Trade history** (every pair read over the last seven days, named in the tab, paged), and
   **Positions** (Futures, with close at market) or **Assets** (Spot holdings).
5. Below the chart, the **Equity** chart draws the venue's equity curve, the session's backlog first
   and then each new sample.
6. While the desk is open, the venue's events keep it current: a fill updates Open orders,
   re-reads the histories and the order panel's balances; a position change updates Positions; a holdings change updates Assets;
   each fill is marked on the chart of its symbol; a strategy's order the app blocked is said in
   the tabs' message line.
7. An order the trader places on the desk joins Open orders as soon as the venue accepts it.

## 4. What must be true afterwards

- Every figure and row on a desk is its own venue's: a Spot fill never appears on the Futures desk
  and the reverse, with both desks open at once.
- Re-opening a desk shows the account as the venue reports it then, orders placed elsewhere
  included; nothing is remembered from the previous visit.

## 5. When it goes wrong

| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| The venue is not enabled | The desk says "… Testnet is not enabled — turn it on in Settings, then restart the app" and holds nothing that could send an order | A route that vanished from the menu would say nothing at all |
| The account cannot be read when the desk opens | The summary is marked "Out of date: the account could not be read", and shows no figure it does not have | An empty panel would read as a zero balance |
| The venue reports the summary stale later | The figures stay, marked "Out of date: <the venue's reason>", until the next change clears the mark | The last known figures are still the best information, said to be old |
| A history read fails | The tab says the read failed | An empty table would read as no history |
| The Spot account's value cannot be priced | The summary says the value is unknown | A sum over unpriced assets would be wrong |
| A cancel or close is refused by a safety gate | The tabs' message names the gate; the rows stay | The order or position is still there |

## 6. What this use case does NOT promise

- No history older than seven days, and no pair the app does not read (the tab names the pairs).
- No account figures in the app's own bookkeeping: every figure is the venue's answer or event.
- No equity history across restarts: the curve is this session's samples.
- No live market data on a desk whose venue's trading is off: its chart shows stored candles.

## 7. Ports and modules it exercises

`trading`: `IVenueTradingPorts` (per venue: `IAccountActivity`, `IAccountSnapshot`,
`IOrderSubmission`, `IEquityCurve`), `AccountSummaryChangedEvent` / `AccountSummaryStaleEvent`,
`OrderFilledEvent` / `OrderEndedEvent` / `PositionChangedEvent` / `HoldingsChangedEvent` /
`LiveOrderBlockedEvent` / `EquitySampledEvent`, each carrying its venue. `market_data`:
`IHistoricalKlines`, `IMarketStream`.

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| The summary's figures per market, read on open, marked stale with its reason, other venues' marks ignored | `tests/unit/modules/trading/ui/desk/test_account_summary.py` | unit |
| The tabs list orders placed elsewhere, open both histories over seven days, page them, follow a fill, list Spot assets | `tests/unit/modules/trading/ui/desk/test_account_tabs_presenter.py` | unit |
| Cancel one, cancel all, close at market, each refused in words by a gate | `tests/unit/modules/trading/ui/desk/test_account_tab_actions_presenter.py` | unit |
| A history tab names what it read and pages honestly | `tests/unit/modules/trading/ui/desk/test_history_view.py` | unit |
| The equity chart: backlog, live samples, a sample during the read not lost (`BUG-100`) | `tests/unit/modules/trading/ui/desk/test_desk_equity.py` | unit |
| Fills marked per symbol, the order panel re-read after a fill, equity per venue, a blocked order said, only the desk's market's candles | `tests/unit/modules/trading/ui/desk/test_desk_live_feeds.py` | unit |
| An order placed on the desk is listed, then cancelled; a filled one is never listed open | `tests/unit/modules/trading/ui/desk/test_desk_journeys.py` | unit |
| Two desks open at once stay apart | `tests/unit/modules/trading/ui/desk/test_two_desks_stay_apart.py` | unit |
| A disabled venue's desk says so and holds nothing that sends | `tests/unit/modules/trading/ui/desk/test_desk_screen.py` | unit |
| Against a fake Binance server: a desk opened later lists and cancels orders placed elsewhere | `tests/integration/application/test_account_tabs_against_fake_server.py` | integration |
| A real account | **the user runs it**: with Testnet credentials and the venue enabled, open its desk and compare the summary, open orders and positions/assets with the Testnet web UI | human |
