# EPIC-026L — An account-level loss cap stops every bot at the owner's figure and keeps them stopped until the owner acknowledges

**Status:** 🟡 In progress (built 2026-10-20; pull request open, the gate and the independent review pending)
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.2 row 5; ADR D9; the user (2026-09-20):
*"hãy cho lô trình để có thể giao dịch thật"*. **Re-scoped 2026-10-20** to the shape the owner pre-approved
(*"co gi can confirm thi cu lam theo de xuat cua ban"*): decision N3 of
[`REVIEW_2026-10-20_what_is_still_missing.md`](../REVIEW_2026-10-20_what_is_still_missing.md) (must-have 3) and
answer O3 of [`DECISION_2026-09-20_mainnet_venue.md`](../DECISION_2026-09-20_mainnet_venue.md) §4a.
**Risk:** 🔴 — it stops every bot without a human, and on a position venue it closes positions; a wrong sum trips it
on a winning day or never trips it on a losing one, and a cap that goes quiet when it cannot see is worse than none.
**Complexity:** M — one pure ledger and policy, one service on the existing ticker, one record file, one refusal in
the runner, one host command.
**Epic:** [`EPIC-026`](../README.md)
**Depends on:** None. (Was `EPIC-026G`, the trade journal; the cap keeps its one record itself.)

---

## 0. What the old text said, and what is dropped

The 2026-09 text was written for the EMA strategy path on `trading`'s session: a daily-loss **and drawdown**
breaker that tripped `EmergencyStopCommand`, journalled its state in the trade journal (`EPIC-026G`), refused
`EnableTradingCommand` with a new `BREAKER_TRIPPED` until the UTC day rolled over, showed two live values on the
Trading screen, tripped on a failed protective-stop placement, and shipped a `breaker-drill` command. The product is
now Grid bots, so this task is the **reduced** one the review asks for. Of the old text:

| Old text | Now |
| :--- | :--- |
| `max_drawdown_percent`, peak-to-trough on the equity samples | **Dropped.** The review: "a drawdown percentage can follow". Seam: one more reason in `LossCapTripReason` and one more test in `loss_cap_policy.py`. |
| Trip dispatches `EmergencyStopCommand` | **Dropped.** The trip dispatches the Bots tab's own `StopBotCommand` per bot. No new close path, no Emergency Stop (which closes positions account-wide and disables the session). |
| `breaker_state` journalled; depends on `EPIC-026G` | **Dropped.** One record file, `state/loss_cap.json` (the day's ledger and the trip). No journal, no database. |
| `EnableTradingCommand` refuses with `BREAKER_TRIPPED` | **Moved.** `BotRunner.start` and `resume` refuse with `BotRefusal.LOSS_CAP_TRIPPED`, the one place every start and resume passes. The trading session's enable is untouched. |
| Refusal ends when the UTC day rolls over | **Changed.** It ends only when the **owner acknowledges** (`bot loss-cap-ack`); a restart, a day roll-over and removing the figure do not clear it. |
| `trading.max_daily_loss_usdt`, a default-free threshold in USDT | **Changed.** `bots.account_loss_cap`, one text, an amount and its quote asset (`"500 USDT"`), **no default**: unset = off. |
| Daily PnL from the journal's fills (realised) | **Changed.** Realised **plus unrealised**, from the bots' own run accounts (`RunEarnings.total_pnl`), summed over every bot of the host since 00:00 UTC. |
| Trading screen shows two live values against their limits | **Dropped for the screen;** the health snapshot's `loss_cap` section and the pre-flight say the figure and whether it is tripped. The day's result is deliberately **not** in the snapshot file (the section collector refuses a `pnl` key). |
| A protective-stop placement failure trips it with its own reason | **Dropped.** `EPIC-039L` halts and closes on that failure already; the cap is the control that does not depend on it. |
| `main.py breaker-drill` | **Dropped.** The composed-app test on the fake exchange is the drill; the owner's Testnet drill is "set a small figure, let a bot lose it" and is listed in §5. |
| `SPEC-004` §5 / `SPEC-007` §1 rows; `CircuitBreakerTrippedEvent` | **Dropped / renamed.** Neither spec describes bots; the event is `AccountLossCapTrippedEvent`. |

## 1. Context and problem

The four session limits (`trading_limit_policy.py`) are counts, a notional and an interval; the per-bot budget caps
what one bot may put at risk; none reads a **day's loss across bots**. A strategy that is wrong all day, or three
bots that are each within budget and all losing, are stopped by a human noticing. The review ranks this must-have 3:
"the only control that does not depend on a bot's own logic being right". It needs the owner's figure (O3), which
this task does not invent: unset = off, and the pre-flight says so (a WARN when the host runs a mainnet venue).

## 2. Acceptance criteria

- [x] **One figure, the owner's, no default.** `bots.account_loss_cap` (`"500 USDT"`); unset or blank = off; set
      and unreadable = the app does not boot (never "off"). Evidence: `test_loss_cap_figure.py`;
      `test_a_figure_that_is_set_and_unreadable_stops_the_app_from_booting_with_the_cap_unarmed`.
- [x] **The sum is realised plus unrealised since 00:00 UTC over every bot**, a gain offsetting a loss, a new run
      banking the old run's day, a deleted bot keeping what it lost, the day starting again at midnight. Evidence:
      `test_loss_cap_ledger.py` (boundaries: a run that began a second before midnight is not today's).
- [x] **At the figure every bot not at rest is stopped through the existing Stop**, a Spot bot keeping its base,
      a position venue closing at market (the only form its Stop accepts); the trip is recorded **before** the first
      stop; a refused stop is asked again; the owner is alerted once (CRITICAL). Evidence: `test_account_loss_cap.py`,
      the composed `test_the_account_loss_cap_stops_every_bot_on_the_fake_exchange.py`.
- [x] **Exactly at the figure trips; one cent below does not.** `test_loss_cap_policy.py`,
      `test_a_loss_one_cent_below_the_figure_trips_nothing`.
- [x] **No bot starts or resumes while tripped**, through any path that asks the runner (Bots tab, `bot start`,
      `run --start-planned`, `run --resume-recovering`, `bot resume`); a bot that gets going by a path that does not
      ask is stopped again by the next sample. Evidence: `test_runner_holds_while_the_loss_cap_is_tripped.py`;
      `test_a_bot_that_gets_going_while_tripped_is_stopped_again_by_the_next_sample`.
- [x] **It stays tripped across a restart, a day roll-over and an unset figure, until the owner acknowledges.**
      Evidence: `test_the_trip_survives_a_restart_and_stops_what_the_restart_brought_back`,
      `..._survives_a_day_roll_over`, `test_removing_the_figure_is_not_an_acknowledgement`, and the composed
      restart test.
- [x] **The owner acknowledges with `main.py bot loss-cap-ack`**, through the host's command directory; refused when
      not tripped; it starts nothing; the loss so far is accepted and counting starts again. Evidence:
      `test_the_owner_acknowledges_through_the_command_directory_and_only_then_may_a_bot_start`, the codec,
      executor and verb tests.
- [x] **It fails closed.** Unable to judge for two minutes (bots unreadable, a refused bot file, a running bot with
      no price or in another quote asset) trips with its own reason; a record that cannot be read starts the cap
      tripped; a record that cannot be written still trips and stops, and says so at ERROR. Evidence: the "failing
      closed" tests in `test_account_loss_cap.py`.
- [x] **The pre-flight and `status` say it.** `account-loss-cap` check (WARN on a mainnet venue with no figure;
      FAIL on an unreadable figure; WARN when tripped); `loss_cap` health section. Evidence:
      `test_loss_cap_health_and_preflight.py`.
- [ ] **The owner's Testnet drill** (§5): a small figure, a bot allowed to lose it. The owner's, not run.
- [ ] **The desktop can acknowledge.** Not built (§6): not cheap, and the headless host is the real-money path.

## 3. Design

Applies the repository's own patterns, not new machinery (`CONSTITUTION.md` P5): a **watch on the bots ticker**
(`BotPriceWatch`, `SleepWatch`), a **small record file written atomically beside the bots' folder**
(`FileAppliedPlanStore`), a **host command through the command directory** (`bot stop` and its siblings), an
**alert source on a contract event** (`BotAlertSource`), a **pre-flight check and a health section** declared by the
module (`declare_operations`). The Design section of the pull request and `Docs/MODULES/bots/` carry the rest:
[`05-building-blocks.md`](../../../../Docs/MODULES/bots/05-building-blocks.md),
[`06-runtime.md`](../../../../Docs/MODULES/bots/06-runtime.md).

Choices the review left to the author, taken here and open to the owner's veto:

1. **Which stop.** The bots' Stop (`StopBotCommand`), not the trading Emergency Stop: "every bot is stopped through
   the existing stop path". A position venue is stopped with the position closed, because that is the only form its
   Stop accepts; a Spot bot keeps its base, as the host's shutdown stop does. The alert and the runbook say a Spot
   bot's loss can still move after a trip. Selling it would be a second decision the cap does not take for the owner.
2. **What "since 00:00 UTC" means for a bot's run account.** The account is the whole run's; the ledger keeps each
   run's baseline at the first sample (or 0 for a run that began today) and banks a finished run's day.
3. **Fail closed.** A read failure of the PnL must not silently disable the cap (`code/errors.md` §6-7): the grace
   is two minutes (a duration, not an amount of money), then it trips with `NOT_JUDGEABLE`. The alternative, "carry
   on with the last figure", would hide exactly the failure the cap exists for.
4. **Acknowledging accepts the loss.** After an acknowledgement the count starts again from that moment, so one
   figure's worth of further loss trips it again; otherwise the same loss would trip it at once. The owner who wants
   a different figure edits the config and restarts.
5. **The figure is the bots' own account**, at the price each bot last saved (at most 30 s old), sampled every 15 s.
   It is not the exchange's equity. That limit is written in `06-runtime.md` and the runbook; reading the exchange
   instead would add a second source of truth and a new network path on the money path.

## 3a. Reuse

`BotPriceWatch` / `IBotTicker` (the ticker), `GetBotStatusReportQuery` (the one read of the bots), `StopBotCommand`
(the Stop), `FileAppliedPlanStore` (the record's pattern), `HostControlAction` + `DirectoryHostControl` (the
acknowledgement), `BotAlertSource` + `IAlertPublisher` (the alert), `IPreflightCheck` + `IHealthContributor` (the
owner's view), `keep_on_stop_closed_reason` (which venue closes). Checked against `capabilities.md`: no row for
money-at-risk or a loss limit exists; `trading_limit_policy.py` counts orders, not money. Not used: the trade
journal (`EPIC-026G`, not built), `EmergencyStopCommand` (account-wide, closes positions, disables the session).

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/loss_cap/{loss_cap_figure,loss_cap_ledger,loss_cap_policy}.py` | Pure: the figure and its parser, the day's ledger, when it trips |
| `src/modules/bots/application/services/loss_cap/{account_loss_cap,loss_cap_sampler,loss_cap_stopper}.py` | The service on the ticker, the read of the bots, the stops |
| `.../loss_cap/{loss_cap_preflight_check,loss_cap_health_contributor}.py` | What the owner reads |
| `src/modules/bots/adapters/file_loss_cap_store.py`, `contracts/i_loss_cap_{store,hold,status,acknowledgement}.py`, `contracts/loss_cap_status.py` | The record and the narrow ports |
| `src/modules/bots/contracts/events/account_loss_cap_tripped_event.py`, `contracts/bot_command_result.py`, `contracts/host_bot_requests.py` | The event, two refusals, the host command |
| `src/modules/bots/application/services/lifecycle/bot_runner.py` | `start` and `resume` ask `ILossCapHold` first |
| `src/modules/bots/application/use_cases/acknowledge_loss_cap_for_host/` | The acknowledgement's handler |
| `src/modules/bots/composition/{loss_cap_bindings,writable_boot,executor_bindings,command_bindings}.py`, `module.py` | Wiring; the sample is registered on the bots ticker at a writable boot |
| `src/modules/bots/cli/{bot_control_verbs,bot_verbs}.py`, `src/config/cli_commands.json` | `bot loss-cap-ack` |
| `src/core/contracts/host_control.py`, `src/modules/operations/application/{host_command_codec,bot_host_command_executor}.py` | `HostControlAction.ACKNOWLEDGE_LOSS_CAP` on the wire and in the host |
| `src/modules/alerting/{domain/alert_kind,domain/alert_catalog,application/sources/bot_alert_source,module}.py` | `ACCOUNT_LOSS_CAP_TRIPPED`, CRITICAL, about the app |
| `src/config/config_keys.py` | `BOTS_ACCOUNT_LOSS_CAP` |
| `scripts/render_bots_design_tables.py`, `src/support/log_view/template_catalogue.json` | The timing row; the regenerated log catalogue |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Figure, sum, boundaries | `tests/unit/modules/bots/domain/loss_cap/` | unit | at the figure trips, a cent below does not; midnight; new run; deleted bot |
| Trip, stops, stay down, acknowledge, fail closed | `.../application/services/loss_cap/test_account_loss_cap.py` | unit | 30 cases over the real cap, sampler and stopper |
| The runner holds | `test_runner_holds_while_the_loss_cap_is_tripped.py` | unit | refusal; nothing else reached |
| Record on disk | `tests/unit/modules/bots/adapters/test_file_loss_cap_store.py` | unit | exact round trip; unreadable refused, none of the content echoed |
| Wire, host, verb | codec, executor, verb tests | unit | the word, the fixed subject, the host's sentence |
| Composed app, Spot + Futures bots on the fake exchange | `test_the_account_loss_cap_stops_every_bot_on_the_fake_exchange.py` | integration | below: nothing; at: both STOPPED, no resting order, position closed, one event, start refused; restart: still refused; acknowledge through the command directory: a start is accepted; third boot clear; no figure: off; bad figure: no boot |
| Wiring is real | the same file, with the `writable_boot` line removed | mutation | four of the six tests fail (checked) |
| The owner's Testnet drill | the owner sets a small `bots.account_loss_cap` on a Testnet host and lets a bot lose it | human | `[loss-cap] TRIPPED` at CRITICAL, a Discord alert, every bot STOPPED, `bot start` refused, `bot loss-cap-ack` accepted. **Not run.** |

## 6. Docs touched

`Docs/MODULES/bots/`: `README.md` (Built row), `03-context.md` (the event, the host command), `05-building-blocks.md`
(the parts), `06-runtime.md` (the sequence and what the figure is not), `07-deployment.md` (the ticker task, the
file), `08-concepts.md` (the record), `09-decisions.md` (N3), `10-quality.md` (the generated timing row).
`Docs/VOCABULARY/README.md` (**Account-level loss cap**). `Docs/OPERATIONS/headless_runbook.md` (setting it,
the trip, `bot loss-cap-ack`, fail-closed). Not written: a `SPEC-` file (no bot spec exists to extend).

**Known gap, a follow-up:** the **desktop has no Acknowledge command**. `bot loss-cap-ack` reaches only a running
`run` host (the command directory is served by it alone). A desktop-only owner who trips the cap stops the app and
deletes `state/loss_cap.json` by hand, the same decision taken without a button; a Bots-mode command is the follow-up.

## Implementation notes (written when done)

## Resume (optional; while unfinished)

Built and unit/integration-tested on `claude/epic-026l-account-loss-cap`. Pending: the `-Full` gate on GitHub, the
independent review, then the move to `completed/` with the epic README row and the ADR's D9 link (left in place here
because the pull request that records the owner's answers, #604, edits the same table).
