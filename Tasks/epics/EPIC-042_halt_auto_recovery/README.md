# EPIC-042 — A bot halted by a transient cause recovers by itself, through the Resume path, and the owner can resume HALTED bots on the host

- **Status:** 🟡 Phase 1 in progress — design pull request open (2026-10-17); no code yet
- **Repositories:** Elite. No Engine change.
- **Origin:** the owner, 2026-10-17, through the coordinating session, after a live incident: a Spot mainnet Grid on the headless VPS host halted with `price_feed_stale`, the feed was back within minutes (`tick_age_s=1`) and the bot stayed `HALTED`, which only a person's Resume or Stop leaves, and the headless host cannot Resume. His decisions, as relayed: (1) automatic recovery after a transient halt, the feed healthy for 120 s, through the Resume path, at most 3 per rolling 24 h, alerts on each recovery and on exhaustion; (2) `run --resume-halted`; (3) a real state in the lifecycle machine; (4) a general mechanism behind a seam, the attempt history in the bot record, Spot Grid `price_feed_stale` recoverable, Futures nothing; the rate-limit auto-resume's migration recorded as a follow-up.
- **North star:** [`DECISION_2026-10-17_halt_auto_recovery.md`](DECISION_2026-10-17_halt_auto_recovery.md): the state, its events and transitions, the seam, the persistence and the choices still open. The module design is kept in step in [`Docs/MODULES/bots/`](../../../Docs/MODULES/bots/README.md) (Planned parts).
- **Decisions:** [`DECISION_2026-10-17_halt_auto_recovery.md`](DECISION_2026-10-17_halt_auto_recovery.md) (D1–D14).
- **Dependencies:** `EPIC-039L` (another session) changes the halt policy and the Emergency Stop order (C3) and removes the Futures-mainnet lock (C4-lite); this epic touches no Futures halt or close behaviour and rebases onto whatever lands first. `EPIC-036` (alerting, Built) carries the alerts.

---

## 1. Decisions already made
1. **A real state, `AWAITING_RECOVERY`**, with four new events; never an `if` on `HALTED` (owner; [D3, D7](DECISION_2026-10-17_halt_auto_recovery.md)).
2. **Dwell 120 s continuous, 3 attempts per rolling 24 h, the same propose-and-confirm as a person's Resume; exits stay watched; a crossed stop loss or take profit ends the bot** (owner; D1, D12).
3. **A general mechanism, layered**: the transient reasons are plain data composed from a common, a kind and a venue layer, later layers winning; a probe per reason says when it has cleared; the attempt ledger lives in the bot record (owner; D4, D15).
4. **Spot keeps the common set (`price_feed_stale`, `user_stream_down`); Futures removes every reason with one line in its venue layer** (owner; D5, D15).
5. **Not migrated here: the grid rate-limit auto-resume** (`EPIC-042F`; D6).
6. **Agent decisions the owner may veto:** a `PAUSED` bot never recovers by itself (D8); a restart ends the wait in `HALTED` (D9, O1); an attempt costs budget when it starts (D10); a 15 min wait limit (D11, O2).

## 2. Goals — measurable
| Metric | Today (measured 2026-10-17, `5a2d0eb`) | When the epic is done |
| :--- | :-: | :-: |
| A Spot Grid halted by a feed gap that then cleared | stays `HALTED` until a person acts | back to `RUNNING` after 120 s of healthy feed, with a fresh ladder, with no person |
| Automatic recoveries of one bot in 24 h | not applicable | at most 3, across restarts; the 4th halt stays `HALTED` and alerts |
| A `HALTED` bot on the headless host | cannot be resumed | `run --resume-halted [--confirm-venue v]` resumes it through the GUI's path |
| States that answer the new condition | 0 | 1 declared state, 4 events, 12 table rows, in `bot_lifecycle_fsm_matrix.py` and the generated tables |
| Futures files changed | not applicable | 0 behaviour changes; a test locks that a Futures venue resolves no rule |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-042A](completed/EPIC-042A_design_and_decision.md) | The design: this epic, the decision record, the module docs and the vocabulary | Elite | None | 🟢 | ✅ Done (2026-10-17; pull request open) |
| [EPIC-042B](incomplete/EPIC-042B_awaiting_recovery_state_and_ledger.md) | The state, the four events and the rows in the lifecycle table; `RecoveryAttempt` in the bot record and its codec; the layer, rule and merge types and the common layer; the generated tables | Elite | 042A | 🟡 | Planned |
| [EPIC-042C](incomplete/EPIC-042C_grid_halt_recovery.md) | The director, the recovery run on the worker, the Spot Grid's rule and probe, the exits re-checked before an attempt | Elite | 042B | 🔴 | Planned |
| [EPIC-042D](incomplete/EPIC-042D_recovery_alerts.md) | `BotAutoRecoveredEvent`, its alert kind and source arm; the exhaustion text on the `BOT_HALTED` alert | Elite | 042B | 🟢 | Planned |
| [EPIC-042E](incomplete/EPIC-042E_run_resume_halted.md) | `run --resume-halted` | Elite | 042B | 🟡 | Planned |
| [EPIC-042G](incomplete/EPIC-042G_bot_show_prints_the_recovery_table.md) | `bot show` prints the bot's effective recovery table | Elite | 042B | 🟢 | Planned |
| [EPIC-042F](incomplete/EPIC-042F_migrate_rate_limit_resume.md) | **Follow-up.** Migrate `GridRateLimitPause` onto the mechanism | Elite | 042C | 🟡 | Planned (not started; record only) |

`042C`, `042D`, `042E` and `042G` are independent of one another once `042B` is in; the order above is by risk.

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 1 Design | The decision, the module docs and the vocabulary merged; the owner has had the chance to veto D8–D11 | Pull request merged; document guards green |
| 2 Mechanism | A bot halted for `price_feed_stale` on the fake exchange recovers after the dwell, ends as Stop when a stop loss was crossed, stays `HALTED` after three recoveries in 24 h across a restart, and raises the alerts | Unit and integration tests named in `042B`–`042D`; `ci-local.ps1 -Full` green on the pull request |
| 3 Host | `run --resume-halted` resumes a `HALTED` fake bot on the fake exchange; a mainnet venue is refused without `--confirm-venue` | Test in `042E`; the owner's Testnet run is the owner's, recorded by the owner |

## 5. Out of scope
- **Futures**: its halt closes the position and `EPIC-039L` governs it. Futures declares no recoverable reason.
- **The rate-limit resume's migration** (`042F`).
- A halt reason other than `price_feed_stale` becoming recoverable: each is one rule and one probe, added with its own evidence.
- Any change to the order session's rule that nothing automatic opens it (`06-runtime.md`): a recovery runs only while the session is open, which a restart closes (D9).

## Notes (newest first)
- **2026-10-17** — The owner's layering requirement (common, kind, venue; merge as data; printable) folded into the design: D15, `042G`. Earlier: epic scaffolded with the design pull request. Real-money behaviour is unchanged until `042C` merges.
