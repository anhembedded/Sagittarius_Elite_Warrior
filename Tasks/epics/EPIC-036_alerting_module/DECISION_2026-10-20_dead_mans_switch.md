# ADR — The dead man's switch is an optional ping to an external monitor, built without EPIC-035W

**Epic:** [EPIC-036](README.md)
**Date:** 2026-10-20
**Status:** Accepted
**Decided by:** the author session of [`EPIC-036E1`](completed/EPIC-036E1_dead_mans_switch.md) as an agent decision under `ONBOARDING.md` §7, within the owner's pre-approval of the coordinator's recommendations on 2026-10-20 (`REVIEW_2026-10-20_what_is_still_missing.md`, must-have 2 and decision N2). **The owner may veto** it; a veto reverts D1–D4 and leaves `EPIC-036E` as it was.
**Supersedes / superseded by (optional):** refines N7 of [the 2026-10-08 decision](DECISION_2026-10-08_alerting_module.md); the secret route is D3 of [the 2026-10-15 decision](DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md).

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree at the commit §1 names |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7 |

## 1. Context
✅ Established, at `a6d950a`: alerts reach Discord only from inside the running process (`alerting/adapters/threaded_delivery_host.py` → `ThreadedDeliveryHost`). If `sew-run` dies, hangs or the VPS powers off, nothing is sent, and resting orders and any Futures position stay on the exchange (`Docs/OPERATIONS/headless_runbook.md` §0, decision O1). The 2026-10-20 review ranks this must-have 2 before the first real-money bot. `EPIC-036E` bundled three things — the switch, a heartbeat message with the bots' health, a daily summary — and waited on `EPIC-035W` for all of them. The switch carries no health content, only liveness, so it has no dependency on `035W`.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **The switch is built now, without `EPIC-035W`.** `EPIC-036E` is split: `036E1` (the switch) ships; `036E` keeps the heartbeat message and the daily summary, which read `035W`'s snapshot | Accepted | 🤖 Agent decision | The must-have closes without the owner's deferred `035W`. The heartbeat body is not invented a second time |
| D2 | **Mechanism: the app POSTs `{}` to an `https` check-in URL every 5 minutes** (`PING_EVERY`); the monitor (healthchecks.io or any service that alerts when its URL goes quiet) tells the owner when the pings stop. The first ping is at start; a failed ping is retried after 1 minute | Accepted | 🤖 Agent decision | Sees a crash, a hang, a power-off and a dead network, which nothing on the host can. Any HTTPS endpoint works; healthchecks.io accepts POST and returns `200 OK` (its documented ping API; limit 5 pings per minute per check, which the 1-minute retry respects) |
| D3 | **Off by default; the URL is a systemd credential `alerting_deadman_ping_url`**, read through `ISecretStore` at each ping (never kept), loaded by `LoadCredential=` like the Discord webhook (D3 of 2026-10-15). Empty or not an `https` URL: off, said once in the log. `deploy/linux/sew-key` is for Binance keys only and is not used | Accepted | 🤖 Agent decision | The URL can fake a heartbeat, so it is a secret: not in the environment, an argument, a log, a reason or an exception. **Cost:** `LoadCredential=` needs the file to exist, so an upgrade creates the (empty) file before the new unit starts, as for the webhook |
| D4 | **A ping is sent only while the alert worker makes progress.** Each delivery lane and the housekeeping pass stamp `WorkerLiveness` after every pass; the beacon pings only if no stamp is older than 5 minutes (`STALL_AFTER`). The beacon is its own thread, so a monitor that is slow or down delays no alert | Accepted | 🤖 Agent decision | A wedged lane stops the ping and the monitor fires, which a bare timer thread would hide. **Limit:** this proves the process and its alert worker are alive, not that each bot is healthy — that is the heartbeat's body (`036E`, after `035W`) |
| D5 | **The monitor being unreachable is reported as a failing channel** (`CHANNEL_FAILING`, id `dead_mans_switch`) once, after 3 failed pings in a row; it never blocks an alert | Accepted | 🤖 Agent decision | If Discord works and the monitor does not, the owner learns the safety net is down. If both are down, only the monitor's own silence helps, which is the design |
| D6 | **No new dependency.** The ping reuses `IWebhookTransport` (`urllib`, `post_json`), and no requirement, lock file, `engine.ref` or Engine file changes | Accepted | 🤖 Agent decision | Nothing for the owner to approve beyond the veto |

## 2a. Constitution check
| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | `test_the_unit_loads_the_dead_mans_switch_url_under_the_name_the_switch_reads` and the generated-unit guard hold the credential; `test_a_wedged_lane_makes_the_worker_not_alive_and_a_released_one_alive_again` holds D4 |
| P2 Verify, don't restate | ✅ | the ping API was read from healthchecks.io's documentation on 2026-10-20, not recalled |
| P3 A copy drifts | ✅ | the secret name is one constant, read by the switch and the unit generator |
| P4 Green proves only what was tested | ✅ | an integration test boots `create_app()` and asserts the POST to the stored URL; the manual kill test is in the runbook and unverified until the owner runs it |
| P5 Apply before you invent | ✅ | a dead man's switch / watchdog heartbeat (Healthchecks, Cronitor); the existing transport, secret stores and credential route |
| P6 Fix the mechanism | ✅ | the ping depends on the worker's progress, not on a free-running timer |
| P7 Seam now, variant later | ✅ | `IWorkerLiveness` is the seam; the heartbeat body and an Options field for the URL are left to `036E` and `036D` |
| P8 Ratchets only fall | ✅ | no test weakened; the log-template catalogue regenerated |
| P9 Decide alone | ✅ | decided here; the veto is the owner's |
| P10 Pyramid and units | ✅ | 5 min ping, 1 min retry, 3 failures, 5 min stall |
| P11 Prompt-grade artifacts | ✅ | this record, the task and the design pages |
| Reversible; no real money, dependency, setting, Engine, user data or secret | ✅ | reversible by reverting the PR; it touches a secret only in that it adds a credential name that is empty (off) until the owner fills it; no dependency, setting or Engine file; no order path |

## 3. Alternatives considered
| Alternative | Why it lost |
| :--- | :--- |
| A systemd `OnFailure=` / `WatchdogSec=` unit or timer on the same VPS | It lives on the host it watches: it cannot see a powered-off or unreachable VPS, the failure that leaves a position open longest |
| The VPS provider's own monitoring | Differs per vendor, is not under the app's control, and watches the machine rather than the app |
| A heartbeat message to Discord only (design §10's first layer) | Needs the owner to notice an absence; the external monitor is the layer that speaks. The message stays in `036E` |
| The owner's second machine running a monitor | The same wire protocol; D2 already allows it (any `https` URL, e.g. a self-hosted push monitor), so nothing is built for it |
| Ping from the housekeeping thread | A slow monitor would delay grouped alerts and the summary by the request timeout, which D4's separate beacon avoids |
| Ping from a free-running timer thread | Keeps pinging while delivery is wedged (the acceptance criterion forbids it) |

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Which monitor, and what period and grace? Recommended: healthchecks.io, period 5 minutes, grace 10 minutes, notification to the same Discord channel and one other (e-mail) | The owner's switch-on, not the code | 2026-10-20 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1–D6 | [`EPIC-036E1`](completed/EPIC-036E1_dead_mans_switch.md) | Built; unit and integration tests green; the kill test on the real VPS not yet run by the owner | the task's notes |
