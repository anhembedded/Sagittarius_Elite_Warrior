# EPIC-035 — A running Spot Grid bot is supervised: it heals, catches up, parks and tells the owner

- **Status:** 🔵 Planned
- **Repositories:** Elite. No Engine change is expected; a need for one gets its own confirmation (`ONBOARDING.md` §2).
- **Origin:** the owner's request for an audit of the Spot Grid bot's exception handling, and its answers of 2026-10-08. The audit (static code review at `master-warrior` `3bbe243`, 2026-10-08, published at https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz) found 6 high, 12 medium and 11 low findings; per-order safety is sound, supervision of a running bot as a whole is not.
- **North star:** [`Docs/SPEC/SPEC-014_run_a_grid_bot.md`](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md); each child updates the SPEC journeys it changes.
- **Decisions:** [`DECISION_2026-10-08_spot_grid_audit_owner_decisions.md`](DECISION_2026-10-08_spot_grid_audit_owner_decisions.md) — D1–D6 accepted.
- **Tracking:** [`TRACKING.md`](TRACKING.md).
- **Dependencies:** Builds on [`EPIC-029`](../EPIC-029_bots_tab_grid_fast_track/README.md) (the Grid bot, its executor, reconciler and stop sequence) and [`EPIC-034`](../EPIC-034_bots_connect_design_run/README.md) (the Connect, Design, Run flow, and mainnet venues). Exchange-side stop-loss stays in [`EPIC-026K`](../EPIC-026_road_to_real_money/README.md): this epic is the app-side supervision that exists until, and beside, it.

---

## 1. Decisions already made
1. Phase 1 is approved and runs under the normal process: feature PRs, the `-Full` gate, a reviewer per PR (D1, owner).
2. Stop-loss stays optional: no default change and no forced warning (D2, owner).
3. The alert channel is Discord, a webhook whose URL lives in the keyring only, behind a notifier port (D3, owner).
4. Start with the price outside the range: **(a)** REFUSED below the lower bound (it would market-buy the whole capital), WARNING only above the upper bound (D4, owner, 2026-10-08).

**Interim operating guidance (the audit's, until Phase 1 ships):** do not run a mainnet bot unattended; keep the bot's chart open and Live whenever a stop-loss is set; after an app restart, open the trading session so the bot reconciles.

## 2. Goals — measurable
| Metric | Today (measured 2026-10-08, static review) | When the epic is done |
| :--- | :-: | :-: |
| Bot states in which stop-loss / take-profit is watched with the chart closed | watched only in RUNNING, PAUSED, HALTED, ERROR and only while a Live chart feeds ticks; never in STARTING, RECOVERING or STOPPING | every state that holds orders |
| A silent price feed (no tick for N s) ends in a named HALT | no staleness rule | yes |
| Exceptions that end the Spot user-data stream for good | any except `OSError` / `ReadLoopClosed` | 0; backoff, health event, HALT after N s down |
| Fills missed in a stream gap, sleep or reconnect are recovered | only at restart or resume | after every reconnect and periodically |
| Ways a placing task can end HALTED / ERROR with orders still resting | 3 (resume refused part-way, STARTING at restart, a failed park write) | 0 |
| Bots that stick in STOPPING | yes (retry only on a session closed→open event) | 0; bounded retry with the reason shown |
| Alerts that reach an absent owner | 0 | HALT, ERROR, stuck, range exit, heartbeat on Discord |
| Signed URLs in cancel-path tracebacks | 0 (`BUG-180` fixed by 035O, 2026-10-08) | 0 |

## 3. Sub-tasks, ordered by risk
Phase 1 is the gate for unattended mainnet; Phases 2–4 follow in order. Each child is one PR.

| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-035A](completed/EPIC-035A_the_bot_owns_its_price_subscription.md) | The bot owns its price subscription, with a staleness rule (H1) | Elite | None | 🔴 | ✅ Done (2026-10-08) |
| [EPIC-035B](completed/EPIC-035B_the_user_data_stream_heals_itself_and_catches_up.md) | The user-data stream heals itself and catches up (H2, H3) | Elite | None | 🔴 | ✅ Done (2026-10-08) |
| [EPIC-035C](completed/EPIC-035C_no_unmanaged_orders_and_no_stuck_states.md) | No unmanaged orders and no stuck states (H4, H5, H6) | Elite | None | 🔴 | ✅ Done (2026-10-08) |
| [EPIC-035D](completed/EPIC-035D_retry_and_backoff_for_exchange_calls.md) | Retry, backoff and `Retry-After` for exchange calls (M3) | Elite | None | 🟡 | ✅ Done (2026-10-08) |
| [EPIC-035E](completed/EPIC-035E_symbol_status_gates_placement.md) | Symbol status gates placement (M5) | Elite | None | 🟡 | ✅ Done (2026-10-08) |
| [EPIC-035F](completed/EPIC-035F_a_revoked_key_is_named_and_alerted.md) | A key revoked mid-run is named, not mistaken for a switch-off (M4) | Elite | 035C | 🟡 | ✅ Done (2026-10-08), alert waits for 035K |
| [EPIC-035G](completed/EPIC-035G_a_failed_store_write_still_parks.md) | A failed store write still parks the ladder (M2) | Elite | 035C | 🟡 | ✅ Done (2026-10-08) |
| [EPIC-035H](completed/EPIC-035H_one_app_instance_per_data_root.md) | One app instance per data root (M6) | Elite | None | 🟡 | ✅ Done (2026-10-08) |
| [EPIC-035I](completed/EPIC-035I_os_sleep_is_detected_and_reconciled.md) | OS sleep is detected and reconciled (M8) | Elite | 035B | 🟡 | ✅ Done (2026-10-08) |
| [EPIC-035J](completed/EPIC-035J_the_reference_price_has_an_age.md) | The reference price has an age (M1) | Elite | 035A | 🟡 | ✅ Done (2026-10-08) |
| [EPIC-035K](cancelled/EPIC-035K_alerts_reach_a_user_who_is_away.md) | ~~Alerts reach a user who is away: a Discord notifier port and adapter (M7)~~ | Elite | — | 🟡 | ❌ Cancelled (2026-10-08), superseded by [EPIC-036](../EPIC-036_alerting_module/README.md): BOT-018's seam is extended into an alerting module instead of a parallel port in `bots` |
| [EPIC-035L](completed/EPIC-035L_range_exit_and_start_outside_the_range.md) | Range exit, and Start with the price outside the range (H7) | Elite | 036B (for the range-exit alert) | 🟡 | ✅ Done (2026-10-08), alert waits for 036B |
| [EPIC-035M](completed/EPIC-035M_pnl_is_complete.md) | PnL is complete: total, BNB fees, HODL benchmark (L2) | Elite | None | 🟢 | ✅ Done (2026-10-08) |
| [EPIC-035N](completed/EPIC-035N_invalid_parameters_are_explained_where_they_are.md) | Invalid parameters are explained where they are (L10) | Elite | None | 🟢 | ✅ Done (2026-10-08); status-bar line superseded by 035W |
| [EPIC-035O](completed/EPIC-035O_no_signed_url_in_a_cancel_path_traceback.md) | No signed URL in a cancel-path traceback (M12 / `BUG-180`) | Elite | None | 🟡 | ✅ Done (2026-10-08) |
| [EPIC-035P](completed/EPIC-035P_a_duplicate_partial_fill_counts_once.md) | A duplicate partial fill counts once (L1) | Elite | None | 🟡 | ✅ Done (2026-10-08) |
| [EPIC-035Q](completed/EPIC-035Q_reconcile_reads_the_executed_quantity.md) | The reconciler reads the executed quantity of an adopted order (M10) | Elite | 035B | 🟡 | ✅ Done (2026-10-08) |
| [EPIC-035R](completed/EPIC-035R_resume_sizes_from_what_is_left.md) | Resume sizes from what is left (M9) | Elite | None | 🟡 | ✅ Done (2026-10-08) |
| [EPIC-035S](completed/EPIC-035S_levels_that_round_together_are_refused.md) | Levels that round to one price are refused (L3) | Elite | None | 🟢 | ✅ Done (2026-10-08) |
| [EPIC-035T](completed/EPIC-035T_a_rejected_counter_order_does_not_kill_the_grid.md) | A rejected counter order does not kill the grid (M11) | Elite | 035C | 🟡 | ✅ Done (2026-10-08) |
| [EPIC-035U](incomplete/EPIC-035U_exchange_filters_are_refreshed.md) | Exchange filters are refreshed during a run (L5) | Elite | 035E | 🟡 | Planned |
| [EPIC-035V](incomplete/EPIC-035V_the_remaining_low_findings.md) | The remaining low findings (L4, L6, L7, L8, L9) | Elite | None | 🟢 | Planned |
| [EPIC-035W](incomplete/EPIC-035W_the_bots_health_is_visible_on_screen.md) | The bot's health is visible on screen: a per-bot strip and a truthful status bar | Elite | 035A, 035B | 🟡 | Planned (owner: not yet) |
| [EPIC-035X](incomplete/EPIC-035X_every_bot_decision_is_in_an_audit_trail.md) | Every bot decision is in an audit trail: a journal port, a Log tab, CSV export | Elite | 035C | 🟡 | Planned (owner: not yet) |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 1 — Running-bot supervision | `035A`, `035B`, `035C` merged: SL/TP watched and a staleness HALT in every order-holding state; the user stream recovers from any exception and reconciles after a reconnect; no placing task ends HALTED / ERROR with orders resting; STOPPING retries | Each child's red-before regression tests (named in the task); the `-Full` run green on each head; a reviewer's read per PR; the owner's Testnet run of a 24 h bot with the chart closed. Not run |
| 2 — Infrastructure resilience | `035D`–`035J` merged: a transient fault no longer ends in ERROR; symbol status, key revocation, store failure, a second instance and sleep are each a named, handled event | Per-child tests; fake-server journeys. Not run |
| 3 — Alerting and transparency | `035L`–`035O`, `035W` and `035X` merged, with the alerts delivered by [`EPIC-036`](../EPIC-036_alerting_module/README.md): the screen shows each bot's feed age, stream state and last reconcile, every decision is in an exportable journal, HALT, ERROR, stuck, range exit and a heartbeat reach Discord; PnL shows the total; the reason for invalid parameters is on the field; no signed URL in a log | A Discord webhook run on the owner's channel; a screenshot of the parameter feedback; the log scan. Not run |
| 4 — Accuracy | `035P`–`035V` merged | Per-child tests. Not run |

## 5. Out of scope
- Exchange-side stop-loss (OCO / STOP_LOSS_LIMIT): [`EPIC-026K`](../EPIC-026_road_to_real_money/README.md). It is the structural answer to H1 while the app is closed; `035A` covers the app-side window only.
- Multiple bots and stream-gap catch-up beyond one bot per symbol: `EPIC-029J`. `035B` pulls the gap catch-up forward for the single-bot case.
- Futures grid, leverage and liquidation guard: `EPIC-029K`. `035B` only checks whether the Futures user-data stream shares H3 and files a bug if it does.
- A default stop-loss or a forced "no stop-loss" warning: the owner decided against both (D2).
- Trailing grid, regime filter (`L11` of the audit): new features, not scheduled.
- A 24-hour Testnet soak of stream latency and the ORDERS rate limit: `EPIC-029H`, waiting on the owner's run.

## Notes (newest first)
- **2026-10-08** — `035O`, `035P` and `035Q` were delivered in one pull request (#447), an exception to "each child is one PR" (§3) made at the coordinator's request so that three small, independent mechanisms share one review and one gate run. They stay three atomic commits (`fix:` for `BUG-180`, one `feat:` each for `035P` and `035Q`), each verified on its own tests.
- **2026-10-08** — The owner requested two more Phase 3 tasks, `035W` (health visible on screen) and `035X` (decision audit trail), and asked that they **not be started yet**; recorded as D5 in the decision file. The epic now has 24 sub-tasks.
- **2026-10-08** — Epic, decision record and 22 sub-tasks written from the audit and the owner's decisions. Phase 1 claims re-verified against the code at `3bbe243`; see each task's Context for the two refinements.
