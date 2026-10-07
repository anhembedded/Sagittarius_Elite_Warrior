# SPEC-004 — The order session opens with the first action that trades, and Emergency stop closes it

- **Status:** ✅ built and proven
- **Actor:** trader
- **Origin:** `EPIC-021G`, with `BUG-088` (a concurrent state change mid-reconciliation) and
  `BUG-089` (a second click landing on an in-flight toggle). Per venue since `EPIC-028B`/`028C`.
  Until `EPIC-034C` this was a switch — *Turn live trading on, and off*; the owner judged the
  switch a redundant step (decision D3 of `EPIC-034`, option A: *"A, làm theo đề xuất của bạn"*) and
  chose to keep its checks inside the actions that need them. Option B, always on with no check,
  was rejected. The file keeps its id and its old name; the use case is what this page describes.
- **Surfaces:** none of its own. It runs inside **Bots → Start**, **Bots → Arm strategy…** and the
  Trade mode's **order panel** (SPEC-014, SPEC-005); **Emergency stop** (Trade menu, `F8`, every
  mode's toolbar) is the only thing that closes it. There is no Enable/Disable trading command,
  toolbar button, title or banner state.

## 1. Trigger

*"I start a bot, arm a strategy, or place an order — and I want to know what my account already
holds before the app sends anything."*

## 2. Preconditions

1. The venue (Futures Testnet or Spot Testnet) is assembled — always, since `EPIC-034B`. A venue
   with no key is assembled too; its check ends this use case at step 3 as `CONNECTION_NOT_READY`.
   Each venue's session is open or closed on its own; opening one never touches the other.
2. Credentials resolve and the exchange is reachable — SPEC-003's check, which this use case runs
   again itself rather than trusting an earlier answer.
3. The session is **closed**, or it is already open and this use case answers at once (step 2).
   It is always closed at start-up: this state is never persisted across runs. It is the one
   setting this app deliberately does not remember.

## 3. Main flow

1. The actor does one of the three things that trade: Start on a bot, Arm strategy, or Buy/Sell on
   an order panel (after its own confirmation, SPEC-005 §3). Each asks `SessionReadiness` first.
2. If the venue's session is already open, the answer is *ready* and nothing is read: reconciling
   again would refuse on the positions this app itself opened and would clear every bot's budget.
3. Otherwise the app runs the connection check. Not reachable, or reachable-but-unusable, ends it.
4. The app reads the whole account back: open positions, and open orders.
5. The app compares that against what it believes. If the exchange holds a position this app has
   no record of, it **refuses** — it does not adopt the position, and it does not close it.
6. The app re-checks that nothing else changed the session while steps 3–5 were on the network.
   If something did — most importantly an Emergency Stop — this attempt loses and answers refused.
7. On success the app opens the venue's session and its user data stream, records what it
   reconciled (on Spot, the holdings baseline), says so on the bus (`TradingSwitchChangedEvent`,
   whose name is the removed switch's) and carries on with the action. A desk's chart goes live.
8. Emergency stop is the mirror and always succeeds: it closes the session first, then cancels,
   closes and reads the account back (SPEC-007, planned). The session stays closed until the next
   of the three actions.

## 4. What must be true afterwards

- When a start, an arm or an order went through, the app's belief about open positions and open
  orders came from **the exchange, moments ago** — or from a reconciliation earlier in the same
  session that nothing has closed since — never from a cached value, and never from an earlier
  session.
- When the session is closed, no order can be submitted live from any surface. Every submission
  path checks this same session state, and the state opens in one place only
  (`test_every_order_is_reconciled.py`).
- Every refusal names itself: the venue cannot place orders, the connection is not ready, there are
  unexpected positions, or a concurrent change superseded the attempt. There is no bare `False`,
  and the screen shows the actor a sentence for each (the ones the switch used).
- An Emergency Stop that lands during a reconciliation **wins**. Silently reopening the session
  right after an Emergency Stop would defeat the button; and an *automated* caller — a bot's tick,
  a strategy's signal — never opens the session at all, so a late order after a stop is refused
  (`TRADING_SWITCH_OFF`, shown as "No order session is open on this venue…").
- The session's three facts — open, orders sent this session, symbols believed open — are read as
  one frozen snapshot. A screen can never observe half of a change made by the websocket thread.

## 5. When it goes wrong

| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| The venue has no key | The action is refused: `CONNECTION_NOT_READY` ("Connection to the exchange is not ready — check your API key/network connection."), the check naming `NOT_CONFIGURED` | The venue is assembled, the key is what it lacks (SPEC-003); no order path reaches it, because every path needs this session open |
| A venue that cannot place orders at all (`TradingVenue.DISABLED`) is addressed | Refused with `TRADING_VENUE_DISABLED` ("This venue cannot place orders.") | Not a venue the app assembles; kept as the refusal for a caller that names it anyway |
| The connection check does not come back ready | Refused: `CONNECTION_NOT_READY` | Includes Hedge mode — "reachable but not usable" is already a named connection failure (SPEC-003) |
| The exchange holds a position this app never sent | Refused: `UNEXPECTED_POSITIONS`, with what was found ("…please handle them manually on the exchange before starting a bot, arming a strategy or placing an order.") | The actor decides what to do about it. Adopting it silently would make the app's limits meaningless; closing it silently would trade without being asked |
| An Emergency Stop is still running on the venue when an action asks to open the session | Refused: `EMERGENCY_STOP_IN_PROGRESS` ("An Emergency stop is still running on this venue — wait for it to finish, then try again.") | The stop closed the session and is still cancelling and selling; reopening it would re-baseline the Spot holdings the stop sells above. The stop marks its run on the venue's session state, and `enable()` itself refuses while it runs |
| An Emergency Stop, or another action, lands mid-reconciliation | Refused: `SUPERSEDED_BY_CONCURRENT_STATE_CHANGE` | `BUG-088`. Reconciliation succeeding does not mean nothing else happened while it ran |
| Two actions start together on a closed venue | One reconciles, the other finds the session open and proceeds | Calls for one venue are serialised, so the second is the "already open" case, not a spurious `SUPERSEDED` |
| An order is sent after an Emergency Stop by a bot or a strategy | The order is refused: `TRADING_SWITCH_OFF`; the bot halts, the strategy's signal is reported as not sent | Only a deliberate action opens the session; an automated caller never does |
| The network drops mid-reconciliation | Refused, with the failure reported; the session stays closed | Closed is the safe end state, and it is the one the app defaults to |

## 6. What this use case does NOT promise

- **Opening the session still reserves nothing** — but the symbol lease exists
  (`EPIC-025` PR 2.1f). It is claimed by *arming a strategy* or *starting a bot*, not by opening
  the session, and what it refuses is an order from anyone else on that symbol: see `SPEC-005` §5.
  Emergency Stop does not release a lease, which is deliberate — a lease tied to the session would
  be released by an Emergency Stop, exactly when an open position most needs the strategy that
  planned its exit to still own the symbol.
- It does not stay open past the app. Closing the app closes it, because this state is never
  persisted; a bot restored by the next start waits (RECOVERING) until one of the three actions
  opens the session again.
- **A start never arms a strategy** (`BOT-166`, the owner's decision of 2026-10-06). The
  configuration last armed on a venue is saved and restored at start — symbol, interval, sizing,
  leverage, parameters — but only as a selection: the Bots mode lists the venue as *Not armed*
  with the saved selection beside it, and Bots → Arm strategy… opens pre-filled with it, so
  re-arming is one action the user confirms in that session. Until then no tick reaches a
  strategy engine. This is not the adoption of a journaled position (`EPIC-026H`, ADR `O2`):
  that happens when the session opens, concerns exchange state, and never starts a strategy.
- It does not promise the reconciled picture stays true. It is a snapshot at open time; the
  account can change underneath, and the app's `known_open_symbols` is deliberately conservative
  — a symbol is marked open the moment an order for it is *sent*, before any fill confirmation,
  because over-blocking a second order is safer than under-blocking one. That holds on a venue with
  positions (Futures); a Spot order never marks its symbol (`BUG-142`), since nothing there could
  clear the mark.
- It does not cancel or close anything. That is Emergency Stop (SPEC-007, planned), which closes
  the session, cancels every open order, closes every position, then reads the account back to
  confirm — and reports each of those three steps separately, because a partial stop is a real
  outcome the actor must see.
- **A mainnet venue asks once.** The first Start (or Resume), arm or manual order on `SPOT_MAINNET` or
  `FUTURES_MAINNET` in a session asks one confirmation that names real money (decisions D3 and D11);
  declining sends nothing, agreeing is remembered for that venue until the app closes, and a testnet
  is never asked. It is a question, not a block: nothing else differs from a testnet
  (`tests/unit/modules/trading/application/test_real_money_consent.py`,
  `tests/unit/modules/bots/ui/bots_screen/test_bots_real_money.py`,
  `tests/unit/modules/trading/ui/desk/test_real_money_order_confirmation.py`).

## 7. Ports and modules it exercises

`trading`: `ITradingSession` — `snapshot()`, `ensure_ready()`, `emergency_stop()` — plus
`SessionReadyResult` and `SessionBlockReason` as the published answer, and `SessionReadiness` (the
application service every opening goes through). Reconciliation reads through
`ITradingAccountReader` and the venue's trading client; the connection gate is SPEC-003's
`IAccountSnapshot`. `bots` (Start) and `strategy` (Arm) reach it through `ITradingSession`;
`ExecuteOrderCommandHandler` calls the service itself for a manual order.

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| Every block reason, including the concurrent-change generation check | `tests/unit/modules/trading/application/session/test_ensure_session_ready.py` | unit |
| An open session is not reconciled again, a stop closes it, the next action reconciles again | `tests/unit/modules/trading/application/session/test_session_readiness.py` | unit |
| Nothing opens the session while an Emergency Stop runs, and the mark is cleared even when the stop raises | `tests/unit/modules/trading/application/session/test_emergency_stop_blocks_opening.py` | unit |
| A manual live order opens the session, a foreign position refuses it before anything is sent, an automated order never reopens a closed session | `tests/unit/modules/trading/application/orders/test_execute_order_opens_session.py` | unit |
| Start opens the session and a refused reconciliation refuses the start | `tests/unit/modules/bots/application/services/test_grid_start_preconditions.py` | unit |
| Arm opens the session; a refused session, and an open position on the symbol, refuse the arm; a disarm is refused only by an open position | `tests/unit/modules/strategy/application/use_cases/test_arm_strategy_session.py` | unit |
| Every live order passes the reconciliation: the session opens in one place, every order needs it open, three actions open it, every live-order caller is declared | `tests/unit/architecture/test_every_order_is_reconciled.py` | architecture guard |
| Both implementations of the port answer the same way | `tests/unit/modules/trading/contracts/test_trading_session_contract.py` | contract |
| One venue's session never moves the other's | `tests/unit/modules/trading/application/test_venue_isolation.py` | unit |
| A session opening puts that venue's desk chart live, and no other's; Emergency stop's async ownership (one at a time, never superseded) | `tests/unit/modules/trading/ui/desk/test_desk_screen.py`, `tests/unit/modules/trading/ui/desk/test_two_desks_stay_apart.py`, `tests/unit/modules/trading/ui/desk/test_desk_session_controls.py` | unit |
| The Trade mode has no command that turns trading on or off | `tests/unit/modules/trading/ui/trade/test_trade_commands.py` | unit |
| The Options page holds no venue control and no restart promise | `tests/unit/modules/trading/ui/settings/test_trading_settings_has_no_venue_control.py` | unit |
| A bot starts in the composed app from a closed session and opens it itself | `tests/integration/modules/bots/test_grid_bot_against_fake_server.py` | integration |
| A start restores a saved strategy as not armed, shows its saved settings, arms it with them on one Arm action, and no tick reaches an engine before | `tests/integration/presentation/ui/test_saved_strategy_restores_disarmed.py`, `tests/unit/modules/strategy/test_module_restores_each_venues_strategy.py` | integration, unit |
| Starting a bot, arming and ordering against a real account | **the user runs it**: with Testnet credentials, start a Spot bot (or place a small order from the Trade mode) with no earlier step and confirm the order appears in the Testnet web UI; with a position the app did not open, confirm the action is refused with the words above. The testnet tier (`tests/testnet/`) was not run in this change: it needs credentials | human |
