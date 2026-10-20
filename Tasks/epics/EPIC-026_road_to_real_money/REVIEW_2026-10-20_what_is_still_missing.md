# EPIC-026 — Review of 2026-10-20: what is still missing before the first real-money bot

**Date:** 2026-10-20
**Asked by:** the owner, through the coordinating session: re-check [`PRO-005`](../../proposal/PRO-005.md)
against today's code and say what is really still missing before trading real money.
**Read at:** `master-warrior` `01d188a`. Every classification below was made by reading the code at
that commit, cited `path` → `symbol` (a point-in-time record, so it is never updated afterwards: later
facts go in a new review). Task files were used only to find where to look.
**Status of the proposal:** unchanged — `PRO-005` stays **Proposed**; accepting it, or retiring it, is the
owner's decision. This review changes no code and no decision.

## 1. Conclusion

`PRO-005` was written for one strategy on one symbol, with nothing but Testnet and an app that had to
survive a human's absence on its own. Since then the product became **grid bots on a headless host**, and
most of the operational half of the proposal was built under other epics. What is left is smaller than the
proposal, different in kind, and mostly the owner's own runs:

- **Built and verified in code:** mainnet venues (the lock `PRO-005` §1.3 asks for is replaced by the
  owner's D11), a withdraw-enabled key refused, a real-money confirmation on every mainnet start, leverage
  and margin set and read back before a Futures bot's first order, an exchange-side protective stop for
  Futures Grid (Long and Short), restart → `RECOVERING` → adopt by tag, a rate-limit pause that resumes
  itself, a user-data-stream watch that halts the bots, liquidation-distance watch, a halt on a position
  the bot cannot see, alerts to Discord, a headless host with a pre-flight, and automatic recovery from
  transient halts.
- **Not built, and a real-money bot wants it:** an alert when the host itself dies or the machine is off
  (`EPIC-036E`), a limit on **how much the whole account may lose** (nothing reads PnL across bots;
  `EPIC-026L` has no code), and a rule for what a manual order does to `RECOVERING` bots (`BOT-197`).
- **Not proven by anyone yet:** the headless checklist (`headless_runbook.md` §11, every row unticked),
  the Futures testnet checks T1–T5, the Spot grid soak (`EPIC-029H`), and the owner's own check of
  mainnet with their key (`EPIC-034E`). These are runs only the owner can make.
- **No longer relevant:** the strategy-edge stage (`EPIC-026D`–`F`, `EPIC-001B`) as written. It judged one
  EMA strategy against TradingView; the product now runs grid bots, whose evidence is a grid backtest and a
  live-versus-backtest comparison on Testnet. The same *question* (is there an edge?) stays, in a lighter
  form (§6, O1).

## 2. `PRO-005` §1, gap by gap

Classes: **DONE** · **PARTLY** · **MISSING** · **NO LONGER RELEVANT**.

| `PRO-005` gap | Class | Evidence (code at `01d188a`) or what is missing |
| :--- | :-: | :--- |
| §1.1 `EPIC-001B` — TradingView diff of the EMA strategy | NO LONGER RELEVANT | Not started (`EPIC-001B` "Chưa làm"). The EMA strategy is still in `strategy/domain/strategies/ema_trend_pullback_strategy.py` and can be armed, but the product the owner runs is the Grid (`bots`). Reopen only if the owner wants the strategy live. |
| §1.1 Out-of-sample / walk-forward / Monte Carlo | PARTLY, NO LONGER RELEVANT for the Grid | Built: a single split (`backtesting/domain/out_of_sample_split.py`), Monte Carlo (`backtesting/contracts/monte_carlo_simulation.py`, `BOT-107B` done). Rolling walk-forward is not built. A Grid has no fitted parameters to over-fit in the same way; its evidence is `bots/application/queries/run_grid_backtest/handler.py` → `RunGridBacktestQueryHandler` and the Futures backtest (`EPIC-039K`). |
| §1.1 "real trading deferred" direction | DONE (reversed) | The owner opened mainnet on 2026-10-07 (`EPIC-034` D11) and Futures mainnet to bots on 2026-10-17 (`EPIC-039L` O2). `Tasks/ROADMAP.md` still carries the 2026-08 block; that is the roadmap's to correct, not this review's. |
| §1.2 Nothing about trading is persisted | PARTLY | Each bot is one atomically written JSON file holding its ladder, held orders, inventory, cost, realised profit, commissions, funding and protective stops: `bots/adapters/persistence/json_bot_store.py` → `JsonBotStore`, `bots/application/kinds/grid/grid_runtime_codec.py`, `bots/domain/grid/grid_runtime.py` → `GridRuntime`. The exchange stays the order and fill truth: the reconcile re-reads open orders and trade history (`recovery/grid_reconciler.py` → `GridReconciler`). **Missing:** a journal of orders, fills and decisions as a record of its own (`EPIC-035X`, Planned, "do not start yet"), and any persisted account-level state (nothing exists to persist, see the circuit breaker). |
| §1.2 Retry, idempotent resend, `recvWindow` | PARTLY | A submit with no readable answer is resolved by the client order id: `trading/application/orders/resolve_unknown_outcome.py` → `place_resolving_unknown`, `resolve_unknown` (`BUG-170`); `FuturesTradingClient.find_order` reads by `origClientOrderId`, then `clientAlgoId`. Rate limits (429, `-1003`, `-1015`, 418) pause and resume the bot: `bots/application/kinds/grid/watch/grid_rate_limit_pause.py`, `bots/domain/grid/rate_limit_pause.py` (`EPIC-035D`). The clock is corrected by a measured offset and measured again on `-1021` (`binance_client_builder.py`, `BUG-111`, `BUG-221`), and the pre-flight fails a skew (`adapters/preflight/clock_skew_check.py` → `ClockSkewCheck`). **Missing:** an explicit `recvWindow` is still sent nowhere in `src/`; python-binance's default applies. Judged low risk given the offset and the pre-flight. |
| §1.2 Leverage never sent to the exchange | DONE (Futures) | `bots/application/services/venue/venue_settings_gate_futures.py` → `FuturesSettingsGate.ensure`: margin type then leverage set through `trading/adapters/binance/futures_account_control.py` → `change_leverage`, `change_margin_type`, read back and compared (`SETTINGS_MISMATCH` refuses the start); Hedge mode refused. |
| §1.2 No protective stop on the exchange | PARTLY | Futures Grid, Long and Short: `bots/application/kinds/grid/protection/protection_futures.py` (`STOP_MARKET`, `closePosition`, mark price), `protected_closer.py` → `ProtectedCloser` (the stop is cancelled only after the position is flat), adopted/replaced/orphan-cancelled on reconcile, and the Emergency Stop keeps it until flat (`trading/application/session/emergency_stop/futures_stop_steps.py`, `EPIC-039L` C2/C3, merged #545/#550). **Missing:** Neutral Futures counts as unprotected until the owner records check T3 (`protective_stop_plan.py` → `NEUTRAL_BOTH_SIDES_VERIFIED = False`); Spot has none by design (`protection_spot.py` → `NoProtection`: a holding is not a leveraged exposure); take-profit stays in the app. |
| §1.2 No daily-loss / drawdown circuit breaker | MISSING | `trading/domain/policies/trading_limit_policy.py` → `TradingLimitPolicy` still reads counts and notional only. Per bot there is a stop-loss price and a budget (`grid_budget.py`) and a cap of 5 active bots per venue (`bots/domain/venue_bot_cap.py` → `MAX_ACTIVE_BOTS_PER_VENUE`); a Futures bot also halts on liquidation distance (below). Nothing sums the loss of the **account** or of the day and stops the bots. |
| §1.2 No out-of-band alerting, no watchdog | PARTLY | Discord is the channel (`EPIC-036` D1): `alerting/adapters/discord_webhook_channel.py`; a bot entering `HALTED`, `ERROR`, a stop that gave up, a stop-loss / take-profit / range exit and the recovery events become alerts (every other halt reason, a rate limit or a lost stream among them, arrives as the generic bot halt) (`alerting/application/sources/bot_alert_source.py`; kinds in `alerting/domain/alert_kind.py`). The watchdog is built: `bots/application/services/watches/user_stream_watch.py` → `UserStreamWatch` halts every bot of a venue when the stream is down past a limit, reconciles on reconnect and on a period; `grid_key_probe.py` halts on a rejected key; `grid_risk_watch.py` halts on liquidation risk or an unobservable position. **Missing:** a heartbeat / dead man's switch (`EPIC-036E`, Planned; the runbook §0 says the host "is not supported for unattended money" until it and `EPIC-036B` land), so process death or a powered-off machine reaches nobody; stream and system sources as alerts of their own (`EPIC-036B`; today a stream-down halt arrives as a generic bot halt). The old Telegram channel still serves `BOT-018`'s sync/UI failures (`shell/composition_root.py`). |
| §1.2 Session factory hard-codes Testnet | DONE | `trading/adapters/binance/binance_client_builder.py` takes the venue; `support/binance_gateway/contracts/trading_venue.py` → `TradingVenue` has `FUTURES_MAINNET`, `SPOT_MAINNET`. |
| §1.3 Mainnet does not exist as a type | DONE | Same enum; `EPIC-034E` is "built and proven on the fake server, only the owner's check with their own key remains". Not done: ADR D5's smaller caps and typed acknowledgement (dropped by D11); a boolean real-money confirmation exists instead (`bots/application/use_cases/start_bot/handler.py` refuses `REAL_MONEY_NOT_CONFIRMED`; the host's variant `start_bot_for_host/handler.py`). |
| §1.4 `SPEC-006`, `007`, `010` reserved | PARTLY | The behaviour exists with tests: `trading/application/orders/cancel_order/handler.py` → `CancelOrderCommandHandler` (`tests/unit/modules/trading/application/orders/test_cancel_order.py`); `session/emergency_stop/handler.py` → `EmergencyStopCommandHandler` (`tests/unit/modules/trading/application/session/test_emergency_stop*.py`); `strategy/application/use_cases/arm_strategy`, `disarm_strategy` (`tests/unit/modules/strategy/application/use_cases/test_arm_strategy_session.py`). **Missing:** the three SPEC files; `Docs/SPEC/README.md` still lists them 🔵. `SPEC-004` and `SPEC-014` cover Emergency Stop and a bot's stop in part. |

## 3. `EPIC-026` sub-tasks

| Id | Class | Where it stands |
| :--- | :-: | :--- |
| 026A SPEC-006 cancel one order | PARTLY | Code and tests above; SPEC file not written. Docs, S. |
| 026B SPEC-007 Emergency Stop | PARTLY | Same; `SPEC-004` covers the session close. Docs, S. |
| 026C SPEC-010 arm / disarm | PARTLY, low value | Same. The strategy path is not the real-money product; write it when the strategy is. S. |
| 026D edge thresholds (O1) | NO LONGER RELEVANT as written | Thresholds for an EMA candidate. See O1 for the grid form. |
| 026E rolling walk-forward | NO LONGER RELEVANT | §2 row 2. |
| 026F candidate report | NO LONGER RELEVANT | Replaced by `EPIC-029H`'s record-versus-backtest comparison, which the owner has not run. |
| 026G trade journal (SQLite) | PARTLY, design changed | Per-bot JSON store instead of SQLite (§2 row 4). A decision/fill journal is `EPIC-035X`. No breaker state exists to journal. |
| 026H crash recovery adopts positions (O2) | DONE (differently) | `bots/application/services/lifecycle/bot_restore_service.py` → `BotRestoreService` and `bot_boot_recovery.py` put a bot back `RECOVERING`; on the owner's Resume, `GridResumeSequence` reconciles by tag and sizes from what is left; the Futures stop is re-protected after a crash (`EPIC-039L` C2). `BOT-183` (done) keeps one bot's Resume from waking the others. Open: `BOT-197`. |
| 026I resilient submission | PARTLY | §2 row 5; only the explicit `recvWindow` is absent. |
| 026J leverage / margin on exchange | DONE | §2 row 6, Futures. |
| 026K exchange-side protective stop | PARTLY | §2 row 7. Task file still says Backlog with "no code"; the bot's stop is the delivery (`EPIC-039L`). |
| 026L daily-loss circuit breaker | MISSING | §2 row 8. |
| 026M out-of-band alerting (O4) | DONE for halts, PARTLY otherwise | Discord, not Telegram (`EPIC-036` D1). |
| 026N user-data-stream watchdog | DONE | `UserStreamWatch`; the alert for it is `EPIC-036B`. |
| 026O reconciliation script and 14-day soak | NO LONGER RELEVANT (soak) / PARTLY | D6 was rejected on 2026-10-07. The reconcile exists in the bot (`GridReconciler`); there is no account-versus-record script. The optional 14-day Futures testnet soak is a runbook (`Docs/OPERATIONS/futures_testnet_soak.md`), not run. |
| 026P mainnet member and factory parameter | DONE | Delivered by `EPIC-034E`. |
| 026Q mainnet caps, typed acknowledgement (O3) | NO LONGER RELEVANT as written | D11 dropped both. The per-bot budget and the real-money confirmation exist; see O3. |
| 026R mainnet read-only first contact | DONE in code, owner's check pending | `api_restrictions_key_gate.py` → `ApiRestrictionsKeyGate` refuses a key that can withdraw; `adapters/preflight/no_withdraw_permission_check.py` does the same in the pre-flight; the owner's check with their own key is `EPIC-034E`'s last box. |
| 026S live-versus-backtest report | MISSING | Needs a live run first (`EPIC-029H`); the Grid backtest to compare against exists. |

## 4. What a real-money grid bot on a VPS needs that `PRO-005` never listed

| Need | Class | Evidence or gap |
| :--- | :-: | :--- |
| Soak result on the target host | MISSING | `headless_runbook.md` §11 (12 rows, all ☐, "not run yet"); `EPIC-029H` soak (24 h, two restarts, one Emergency Stop) not run; Futures checks T1–T5 not run. Not proven under real systemd (§12). |
| Dead man's switch / heartbeat | MISSING | `EPIC-036E`, Planned. |
| Account-level loss cap | MISSING | §2 row 8. |
| Liquidation-distance alert | PARTLY | The guard and the halt are built: `grid_risk_watch.py`, `bots/application/services/risk/risk_guard_futures.py`; `CRITICAL` halts with `LIQUIDATION_RISK` (and so alerts as a bot halt). The earlier levels (`BotRiskChangedEvent`) reach no channel, and `AlertKind` has no liquidation kind. |
| Per-account order-rate and weight safety | DONE | Cap of 5 bots per venue (`MAX_ACTIVE_BOTS_PER_VENUE`), the rate-limit pause, per-bot owner budgets (`trading/application/session/register_owner_budget`). |
| API-key permissions and address | DONE | Withdraw refused (above); the pre-flight names the address the exchange saw when it refuses a key that is restricted to other addresses (`adapters/preflight/outbound_address_check.py`) and checks that credentials are present. Keys live in systemd credentials or the OS keyring (`src/support/secrets`, `EPIC-038E`). |
| Key rotation | PARTLY | Only the Discord webhook has a rotation procedure (`headless_runbook.md` §3). Rotating an **API key** (revoke, enrol, restart, what happens to resting orders) is not written. Docs, S. |
| Backup of `/var/lib/sew` | PARTLY | Only a manual `cp -a state` before an upgrade (`headless_runbook.md` §8 step 3). No scheduled backup, no restore drill. Losing `state/bots/` leaves tagged orders on the exchange that no bot manages. Docs + a timer, S. |
| Host survives restart, upgrade, rollback | DONE in code, unproven on a machine | `operations/application/run_host.py` → `RunHost`, `host_state_machine.py`, `preflight_runner.py`; §11 rows 2, 3, 10 are the proof. |
| A restart or manual order must not start a bot the owner did not resume | PARTLY | `BOT-183` done; `BOT-197` (Backlog, P2, 🔴, S) is the open half: a desk order or a strategy arm that opens a closed session still reconciles every `RECOVERING` bot of the venue. |
| Transient halts recover without a person | DONE, Testnet run pending | `EPIC-042`: `bots/application/services/lifecycle/halt_recovery_director.py` → `HaltRecoveryDirector`, `grid_halt_recovery.py` → `GridHaltRecovery`. Whether to let a real-money bot do this is an owner choice (the owner asked for it on 2026-10-17); the `042F` Testnet run is open. |
| The owner can see health at a glance | PARTLY | `bot list` / `bot show` and the health line exist; the on-screen health (`EPIC-035W`) is Planned. |
| Spot Grid inventory in a crash | ACCEPTED RISK | No exchange-side protection by design (`NoProtection`); resting orders stay on the exchange when the host stops (`operations/adapters/leave_orders_resting.py`). The owner decided this on 2026-10-17 (O12) for Futures; the same reasoning is not recorded for Spot. |

## 5. Ranked: before the first real-money bot, and what can follow

Size is the build effort (S ≈ a day, M ≈ a few days, L ≈ a week or more); "owner" means the owner's own time and no code.

### Must have

| # | Item | Size | Why it cannot follow |
| :-: | :--- | :-: | :--- |
| 1 | Run `headless_runbook.md` §11 on the real Linux VPS on a testnet venue and sign it (kill -9, reboot, stop, upgrade/rollback, pre-flight failures) | owner, S | Nothing has run under systemd; the runbook itself says the host is unsupported for unattended money. |
| 2 | `EPIC-036E` heartbeat and dead man's switch | M | Without it a dead process or a powered-off VPS is silent, and resting orders and any Futures position stay on the exchange. Row 12 of §11 depends on it. |
| 3 | An account-level loss cap: when the day's (or the run's) total loss across the host's bots passes a figure the owner sets, stop every bot through the existing stop path and refuse a restart until the owner acknowledges (`EPIC-026L` reduced to this; no new close path) | M (L if it needs persisted day state) | The only control that does not depend on a bot's own logic being right. It needs the owner's figure (O3). |
| 4 | `BOT-197`: decide the rule, then build it | S | A real-money bot must never start from someone else's action. |
| 5 | Futures: run T1, T2, T4, T5 on testnet (`futures_testnet_soak.md`), and T3 if any Neutral bot will hold a position | owner, S | The protective stop's behaviour through a zero position and the event order are unverified; leverage above 1 on mainnet rests on them. |
| 6 | `EPIC-029H` Spot soak (24 h, two restarts, an Emergency Stop) or the Futures equivalent, with the record compared to the backtest | owner, S | The only evidence the bot behaves on the real exchange as it did on the fake one; it is also `EPIC-026S`'s first input. |
| 7 | `EPIC-034E`: the owner's check of mainnet with their own restricted key | owner, S | The last box of the mainnet epic. |
| 8 | Write API-key rotation and a state backup/restore into the runbook, and take one backup before the first real run | S | A leaked key or a lost state directory is the two failures with no written answer. |

### Can follow

| Item | Size |
| :--- | :-: |
| `EPIC-036B` stream/system alert sources, liquidation warnings reaching Discord | M |
| `EPIC-035W` on-screen health; `EPIC-035X` audit trail (the decision journal) | M; L |
| `EPIC-036C` Telegram into the alerting module; `EPIC-036D` alerts UI; `EPIC-036F` remote control | M; M; L |
| Neutral Futures protection (waits for T3) | S after T3 |
| `EPIC-042F` Testnet run | owner, S |
| `SPEC-006`, `007`, `010` written (`EPIC-026A`–`C`) | S each |
| Explicit `recvWindow` | S |
| `EPIC-026S` live-versus-backtest report, repeated per capital step | S per step, after a live run |
| Rolling walk-forward and the TradingView diff (`EPIC-026E`, `EPIC-001B`), only if the EMA strategy goes live | M; M |
| `EPIC-039M` kind conformance for profiles | M |

## 6. Owner decisions still open (the ADR's O1–O4)

| # | Question | Options | Recommendation |
| :-: | :--- | :--- | :--- |
| O1 | The edge gate. The ADR asked for profit factor, drawdown and trade-count thresholds for an EMA candidate. | (a) keep it as written, for the EMA strategy only; (b) replace it for Grid bots by a checklist the owner signs once per bot design: the backtest beats buy-and-hold net of fees over the same window (`bots/domain/grid/buy_and_hold.py`, `futures_benchmark.py` exist), and the 24 h testnet record sits within a tolerance of its backtest; (c) no gate, the owner's risk (D11's spirit). | (b). It costs no code, answers the same question for the product that exists, and the figures it needs are already printed. The tolerance is the owner's number. |
| O2 | After a restart with an open position, adopt it or refuse? | (a) refuse; (b) adopt by tag, automatically; (c) adopt by tag **on the owner's Resume** (today), with transient halts recovering by themselves (`EPIC-042`). | (c). It is what the code does and what the owner decided for the host (`EPIC-038` O2); record it as the answer and close O2. `BOT-197` is the one hole in it. |
| O3 | The first real-money stage: capital, leverage ceiling, per-order notional, daily-loss cap. | (a) the per-bot budget alone, as today; (b) (a) plus an account-level loss cap (must-have 3) and a leverage ceiling constant for the first bot, in the style of `MAX_ACTIVE_BOTS_PER_VENUE`; (c) restore ADR D5's venue caps and typed acknowledgement, which D11 dropped. | (b), with the first bot on Spot or on Futures at 1× so the unverified Futures checks are not on the critical path. The figures are the owner's; size the first bot so that its full stop-loss loss is an amount the owner can lose without consequence. |
| O4 | The alerting channel. | Telegram (the ADR's pick) or Discord. | Already answered: Discord first (`EPIC-036` D1), Telegram later (`EPIC-036C`). Record it and close O4. |

Further decisions this review surfaced, none yet asked: whether a real-money bot may leave a Spot
inventory behind a dead host (the Futures answer exists, O12); and whether `EPIC-026` is retired in favour
of the must-have list above (recommended: keep it as the home of must-haves 3, 4 and 8 and mark the stale
sub-tasks, rather than open an epic for a list of eight).

## 7. Records found stale while reading (not corrected here)

- `Tasks/epics/EPIC-039_futures_venue_profile/incomplete/EPIC-039L_*.md` status line says C3 (#550) and C4-lite (#551) are "in review"; both are merged (`c24be86`, `42ca328`).
- `EPIC-026K`'s file says there is no code; the delivered stop is `EPIC-039L`'s.
- `Tasks/ROADMAP.md` still carries the 2026-08 "real trading deferred" block.
- `Docs/OPERATIONS/headless_runbook.md` §0 and `EPIC-036` agree that unattended money waits on `EPIC-036B`/`036E`; this review treats `036E` as the must-have and `036B` as a follow-up because a halt already reaches Discord.
