# EPIC-029H — One Grid bot trades on Spot Testnet across restarts and an Emergency Stop, and its record matches the backtest of the same period

**Status:** 🟡 In progress: the agent's part is in PR7. The soak, the report and the backtest comparison wait on the user's run.
**Source:** [`PRO-006`](../../../proposal/PRO-006.md). This is the fast track's goal: *"để nhanh
chóng giao dịch thật"*, trading for real, which means on Spot Testnet (the user, 2026-10-03).
**Risk:** 🟡 — Testnet liquidity and price paths differ from mainnet. The soak proves mechanics,
not profitability.
**Complexity:** M — a gated Testnet test, a soak procedure the user runs, and a written report.
**Epic:** [EPIC-029](../README.md)
**Depends on:** `EPIC-029E`, `EPIC-029F` and `EPIC-029G`. `EPIC-029D` is needed for the comparison.

---

## 1. Context and problem

The fake exchange proves the logic. Only a real exchange API proves these:

- acceptance;
- partial fills;
- the cancel payload (ADR D8);
- the order rate;
- behaviour across a restart.

`EPIC-028N` established the tier: `tests/testnet/`, gated by `SEW_TESTNET_TESTS=1`, run by the
user with their own keys.

## 2. Acceptance criteria

- [x] **Precondition: the tab drives the real executor.** On the fake exchange, an integration test
  drives the Bots tab's Start, Pause, Stop and Resume through the real `EPIC-029E` executor.
- [ ] **Gated Testnet test** (written in PR7; met when the user's run returns it green). `tests/testnet/test_grid_bot_round_trip.py` runs a narrow grid (4
  levels, around the last price, at the minimum notional). It asserts:
  - every level is RESTING on the exchange, with the bot's tag;
  - a cancel from outside is re-placed;
  - Stop cancels everything and leaves no tagged open order.
- [ ] **Soak.** The user runs one Grid bot for at least 24 hours on Spot Testnet, with at least
  two app restarts and one Emergency Stop followed by a confirmed re-plan.
- [ ] **The user-data stream's latency on Testnet** (handed over by `EPIC-029E`, whose start
  counts the opening base only once its fill arrives on the stream). The gated test records the
  latency of a cancel heard on the stream, and the time from Start to Running
  (`logs/testnet/spot_grid_round_trip.json`); the report states both.
- [ ] **The venue's `ORDERS` rate limits** (handed over by `EPIC-029A`, which could not reach
  Binance from its build container). Read `exchangeInfo.rateLimits` on Spot Testnet, record the
  `ORDERS` limits and `MAX_NUM_ORDERS`, and check them against the O1 caps; state whether several
  bots on one account need an account-wide cap, since the caps bound each budget, not the account.
- [ ] **Soak report.** `Tasks/reports/` records:
  - the cycles completed;
  - the realised grid profit against the fills on the exchange's trade history;
  - every HALTED or ERROR, with its cause;
  - the open orders after each restart, against the saved levels.
- [ ] **Backtest comparison.** `EPIC-029D` replayed on the soak period, with the same parameters,
  is set beside the live record. Any difference in cycles is explained by the fill rule or by
  Testnet liquidity. It is never left unexplained.

## 3. Design

- **Same shape as `EPIC-028N`.** The procedure mirrors it: the user sets the Testnet keys
  (never pasted into chat), runs the gated test, then starts the soak from the Bots tab. The
  agent reads the log files the user returns.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `tests/testnet/test_grid_bot_round_trip.py` (new) | gated round trip |
| `tests/testnet/test_spot_rate_limits.py` (new) | gated read: how many owner budgets fit one account |
| `tests/testnet/grid_testnet_app.py` (new) | the composed app on Spot Testnet; the stream probe, state wait and clean-up |
| `tests/integration/modules/bots/test_spot_testnet_boot_on_the_fake_exchange.py` (new) | the testnet composition proven on the fake exchange in CI |
| `Tasks/reports/grid_soak_<date>.md` (new) | soak report |

## 5. Testing

- **The Testnet tier itself, run by the user.** The agent verifies from the log: every expected
  test passed (not skipped), and there was no `Traceback`.

## Implementation notes (written when done)

**The agent's part (PR7, 2026-10-04).**

- `tests/integration/modules/bots/test_bots_tab_drives_the_executor.py`
  - Builds the Bots screen on the composed app's container, over the fake exchange.
  - Presses Start, Pause, Resume and Stop. The commands travel through the real dispatcher, thread pool and `EPIC-029E` executor out to the exchange.
  - Checked by mutation: removing the presenter's send makes the test time out. It also asserts the Stop dialog's answer (sell the base) reached the executor (`sell_base_on_stop`), which the fake's empty book alone could not show (the PR #339 review).
  - The composed-app helpers now live in `grid_fake_exchange.py`, shared with `test_grid_bot_against_fake_server.py`. The `exchange` fixture is in that directory's `conftest.py`.
- `tests/testnet/test_grid_bot_round_trip.py`
  - Boots the app with Spot Testnet on and turns trading on through `EnableTradingCommand`, which starts the user-data websocket.
  - Before Start, proves the user-data stream live: an untagged far-away LIMIT BUY is placed and cancelled until its cancel comes back as an `OrderEndedEvent` (the PR #339 review: the opening buy's fill must arrive on the stream within the pacer's spacing, or the SELL levels are refused). Its latency is recorded.
  - Drives a four-level grid, 5% either side of the last price, with every order at four times the minimum notional. A wait fails at once, with the runtime's reason, when the bot halts or errs. It asserts that:
    - every level rests with the bot's tag;
    - a level cancelled from outside is laid again under a new id;
    - Stop, selling the base, leaves no tagged order open.
  - Clean-up stops a bot still running (selling its base) before cancelling what is left, since a cancel heard while RUNNING is laid again; a clean-up failure is logged, never masking the test's own.
  - The stream probe, the state wait and the clean-up live in `tests/testnet/grid_testnet_app.py`, so the test file stays under the 400-line ceiling (the PR #339 round-2 review).
- `tests/testnet/test_spot_rate_limits.py`
  - Reads `exchangeInfo.rateLimits` and the symbol's `MAX_NUM_ORDERS` and works out how many owner budgets at the O1 caps fit one account: a burst within each `ORDERS` window (the spacing bounds it) and the open orders. It writes the number to `logs/testnet/spot_rate_limits.json`, which answers whether several bots need an account-wide cap.
  - Not run here: the build container cannot reach Binance. The user's run is the evidence.
- **User's second run (2026-10-04)**, `-TestnetOnly`, on `master-warrior` after PR7:
  - `test_spot_rate_limits.py` passed; its report is `logs/testnet/spot_rate_limits.json`.
  - The grid round trip errored at setup: its fixture asked `IVenueTradingPorts` for a `client_factory`, which only a venue context (`IVenueContexts`) has. No order was sent.
  - Fixed by moving the composition into `grid_testnet_app.composed_on_spot_testnet`, reached through `IVenueContexts`, and proving it on the fake exchange in CI (`test_spot_testnet_boot_on_the_fake_exchange.py`, red with the old line). Enabling trading stays in the person's run: the fake server does not speak the user-data websocket.
  - The four Futures tests still fail with `-2015`, as in the first run.
- **User's first run (2026-10-04)**, `-TestnetOnly`, before PR7:
  - The Spot round trip passed. So the Spot keys resolve and Spot orders are accepted.
  - The four Futures tests failed with `-2015`: the Futures Testnet key was rejected. That needs a new Futures key and is not on this task's path.
  - The app measured a clock skew of about 123 s on the user's machine. Spot signs with the server-time offset (`SpotSessionFactory._sync_timestamp_offset`).

**The soak procedure (the user).** Keys stay out of chat.

1. **Gated test.** Run `$env:SEW_TESTNET_TESTS=1; .\scripts\ci-local.ps1 -TestnetOnly`. Return the `LOG_FILE` and `logs/testnet/spot_rate_limits.json`.
2. **Start the soak.**
   - Run `.\scripts\run-ui.ps1 -Dev`, with Spot Testnet enabled in Settings and the app restarted.
   - Store the daily candles for the symbol (Database tab).
   - On the Bots tab: New bot, then Spot Grid on Spot Testnet. Parameters with no Refused verdict, then Save, then Start, with live trading on for Spot.
3. **During at least 24 hours**, note the time of each event:
   - two app restarts (the bot comes back Recovering, then Running);
   - one Emergency Stop, then Resume, then Confirm resume.
4. **End.** Press Stop. Return the `logs/dev-*.log` files, `state/bots/<id>.json` and the event times.
   - Then the agent writes the report, the `ORDERS` limits against the caps, and the backtest of the same period.

## Resume (optional; while unfinished)
