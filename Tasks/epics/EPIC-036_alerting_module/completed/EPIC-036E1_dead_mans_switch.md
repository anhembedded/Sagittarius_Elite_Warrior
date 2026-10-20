# EPIC-036E1 — A host that dies or powers off reaches the owner: the dead man's switch

**Status:** ✅ Done (2026-10-20) — built and proven by unit and integration tests; the owner's kill test on the VPS is still to run (§5)
**Source:** the coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`, 2026-10-20, from must-have 2 of [`REVIEW_2026-10-20_what_is_still_missing.md`](../../EPIC-026_road_to_real_money/REVIEW_2026-10-20_what_is_still_missing.md): if `sew-run` dies or the VPS powers off, nothing tells the owner, and resting orders and any Futures position stay on the exchange.
**Risk:** 🟡 — a new outbound ping to a third-party service and one more credential; no order path, no real-money behaviour
**Complexity:** M
**Epic:** [EPIC-036](../README.md); split from [EPIC-036E](../incomplete/EPIC-036E_heartbeat_dead_mans_switch_and_summary.md), which keeps the heartbeat message and the daily summary
**SPEC:** none; the journey is the runbook's §3b
**Design:** [`Docs/MODULES/alerting/`](../../../../Docs/MODULES/alerting/README.md); the decision is [`DECISION_2026-10-20_dead_mans_switch.md`](../DECISION_2026-10-20_dead_mans_switch.md) (an agent decision the owner may veto)
**Depends on:** [EPIC-036A](EPIC-036A_alerting_core.md), [EPIC-036G](EPIC-036G_walking_skeleton_halt_to_discord.md). **Not** on `EPIC-035W`: the switch carries liveness, not health.

---

## 1. Context and problem
An app that dies cannot report that it is dead. Today an alert reaches Discord only from inside the running process. The standard answer is a **dead man's switch**: the app pings an external monitor on a schedule and the monitor alerts the owner when the pings stop. `EPIC-036E` bundled it with a heartbeat message and a daily summary that read `EPIC-035W`'s health snapshot, and waited for it. The switch needs none of that, so it is split off (decision D1) and the two parts that need `035W` stay in `036E`.

## 2. Acceptance criteria
- [x] **A ping every 5 minutes** to an `https` check-in URL while the app is alive, the first one at start; a failed ping is retried after 1 minute. (`test_the_ping_is_sent_every_five_minutes_while_the_worker_is_alive`, `test_a_lost_ping_is_tried_again_after_a_minute_not_after_five`, boundaries at ±1 s)
- [x] **Off by default.** No stored URL, or one that is not `https` with a host: nothing is sent and the start log says so once. (`test_the_dead_mans_switch_is_off_by_default`, `test_a_stored_value_that_is_not_an_https_url_pings_nothing`, `test_what_counts_as_a_check_in_url`)
- [x] **The URL is a secret.** A systemd credential `alerting_deadman_ping_url` via `LoadCredential=`, read through `ISecretStore` at each ping and never kept; in no log line, reason, exception or alert. (`test_the_ping_url_never_appears_in_a_log_or_error`, `test_the_unit_loads_the_dead_mans_switch_url_under_the_name_the_switch_reads`, `test_the_url_is_read_at_each_ping_so_a_rotated_one_is_used`)
- [x] **The ping means the worker is alive, not that a thread exists.** It is sent only while every delivery lane and the housekeeping pass finished a pass in the last 5 minutes. (`test_a_wedged_worker_stops_the_ping_and_a_recovered_one_resumes_it`, `test_a_wedged_lane_makes_the_worker_not_alive_and_a_released_one_alive_again`, `test_a_worker_is_alive_up_to_the_stall_limit_and_not_after`)
- [x] **An unreachable monitor never delays an alert.** The beacon is its own thread. (`test_the_beacon_runs_at_once_and_apart_from_the_lanes`)
- [x] **Its failure is shown as a channel failure**, once, after 3 failed pings in a row; a refused ping (a wrong URL) counts as a failure. (`test_a_monitor_that_stays_down_is_reported_once_as_a_failing_channel`, `test_a_refused_ping_counts_as_a_failure`, `test_a_success_resets_the_count_of_failures_in_a_row`)
- [x] **It is wired in the composed app.** (`test_a_booted_app_with_a_check_in_url_pings_it` over `create_app()`)
- [x] **The owner can switch it on.** Runbook §3b; the generated unit loads the credential; the upgrade note creates the empty file first.
- [x] **Design in step**: `Docs/MODULES/alerting/` changed in the same pull request.
- [ ] **The kill test on the real VPS** (runbook §3b, step 5): the owner stops the host and the monitor alerts. Needs the owner; not run.

## 3. Design
`DeadMansSwitch` (`alerting/application/dead_mans_switch.py`) is not an `IAlertChannel`: it carries liveness, not an alert. `tick()` is called by the beacon thread of `ThreadedDeliveryHost` every 5 s and does no I/O until a ping is due. `WorkerLiveness` (`alerting/adapters/worker_liveness.py`, behind `IWorkerLiveness`) holds one stamp per worker thread; lanes and housekeeping touch it after each pass. The ping is `IWebhookTransport.post_json(url, {})`, so no dependency is added.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/application/dead_mans_switch.py` (new) | The switch, its constants and the secret's name |
| `src/modules/alerting/contracts/i_worker_liveness.py` (new) | The progress port |
| `src/modules/alerting/adapters/worker_liveness.py` (new) | The stamps and the 5-minute stall limit |
| `src/modules/alerting/adapters/threaded_delivery_host.py` | The beacon thread; lanes and housekeeping stamp their passes |
| `src/modules/alerting/composition/alerting_bindings.py` | Wiring |
| `scripts/render_service_files.py`, `deploy/linux/sew-run.service` | The credential, regenerated |
| `Docs/OPERATIONS/headless_runbook.md`, `Docs/MODULES/alerting/` | The steps to switch it on; the design |

## 5. Testing and implementation notes
Unit (fake clock, fake transport, fake liveness and follow-up; the real `ThreadedDeliveryHost` on real threads for the wedge): `tests/unit/modules/alerting/application/test_dead_mans_switch.py`, `adapters/test_worker_liveness.py`, `adapters/test_threaded_delivery_host.py`. Integration over the composed app: `tests/integration/modules/alerting/test_the_composed_app_pings_the_dead_mans_switch.py`.

Mutation checks run on 2026-10-20, each turning the named test red: the beacon bound to a no-op (the integration test); the due check `<` flipped to `<=` (the five-minute test); the lane's `touch` removed (the wedge test); the liveness gate removed (the wedged-worker test).

**Decided, not built:** an Options → Alerts field for the URL (`036D`), the heartbeat message and the daily summary (`036E`), and a signal from the host's own health snapshot into the ping gate (after `035W`). A clean stop sends no "stopping on purpose" signal: the monitor fires after its grace, which is what the owner wants while resting orders stay on the exchange (decision O1); pause the check in the monitor for a planned upgrade.

## Resume
Done. What is left is the owner's: create the monitor, store the URL, run the kill test (runbook §3b) and record the result here.
