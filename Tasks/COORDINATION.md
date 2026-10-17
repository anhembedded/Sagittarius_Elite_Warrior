# Coordination — live state

**Reader:** the coordinator session (`.claude/skills/coordinate/SKILL.md`), which reads this first and updates it after every merge, hand-off or owner decision. **Last updated:** 2026-10-17.

**Coordinator session:** `session_01PZn6EWxn6gytSGKwbuRJGg`. Authors send "ready to merge" here; a new coordinator replaces this line first.

This file holds state, not rules. Rules live in `.claude/`; decisions live in their records. A line here that a record contradicts is wrong: fix the line.

## Owner's standing decisions

| Decision | Where it binds |
| :--- | :--- |
| The coordinator may merge code PRs itself once it has verified the head (gates read, reviewer PASS where one is required, scope matches). Owner's words: *"bạn theo dõi và tự merge hết đi, cho phép"* | `coordinate` skill step 5 |
| Authors run on the cheaper general model; design-heavy work and real-money reviews run on the strongest model; a reviewer is never on the author's model | `coordinate` skill step 3 |
| At most two delivery streams in flight; a weekly digest; design decisions are taught and written to `Docs/LEARNING/` | `report-rule.md` §3 |
| Speak Vietnamese to the owner; repository text in English | `ONBOARDING.md` §10 |
| The model named Fable is never used: not for a session, a created session or a subagent; "strongest model" means the strongest other model (2026-10-17) | `ONBOARDING.md` §7, "Excluded model" |
| EPIC-039L O1: the Emergency Stop cancels regular orders, then closes, then confirms the position is flat, then cancels conditional orders. O2: the Futures mainnet lock is removed with no new mechanism ("tui tự quản rủi ro"). O3 b: take profit stays in-app until after the soak | `Tasks/epics/EPIC-039_futures_venue_profile/DECISION_2026-10-16_futures_protective_stop_minimum.md` §6 |
| EPIC-042: a transient halt waits in `AWAITING_RECOVERY`. Recovery waits for 120 s of continuously clear signal, at most 3 times per 24 h. The policy is layered (common, kind, venue). A restart ends the wait in `HALTED`. A stalled wait raises an alert and keeps waiting | `Tasks/epics/EPIC-042_halt_auto_recovery/DECISION_2026-10-17_halt_auto_recovery.md` |

## Streams in flight

| Stream | Next step | Author session | Reviewer session | PR | Blocked on |
| :--- | :--- | :--- | :--- | :--- | :--- |
| EPIC-042 halt auto-recovery | 042C merged ([#552](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/552)). Next: 042D, 042E, 042G per the epic README's Resume; 042F waits for the owner | `session_01YAKL8J6qPJTqRGHSezUTUe` | spawned per PR by the author | not yet open | nothing |
| EPIC-039L C4-lite | C3 merged ([#550](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/550)). Futures mainnet lock removed (O2); reviewer PASS round 3 at 1956eca; author merging master into the PR | `session_016ToGGUVsE8ESa454e3eb1T` | `session_012XC79LLm2DLs5XrUNhAkyQ` | [#551](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/551) | author's "ready" at the post-merge head |

Deferred: EPIC-039L D10 and D13 (a halt that leaves the position, stop custody).

## Owner still owes

- O12: the headless host's shutdown policy for a Futures bot. (a) leave the position and its exchange stop standing, or (b) close the position first. Coordinator recommends (a). It becomes its own task once the owner answers.

- Sync the Windows clock. It was 127 s ahead on 2026-10-17. Then Stop and Start the Futures Testnet bot again after pulling BUG-223.
- Check Binance Testnet for leftover `SEW-djwx0w` orders.

## Backlog worth remembering

- BOT-182: the desktop app shows a notice when the clock skew exceeds 1 s.
- EPIC-029J: two copies of the app on one account and symbol.
- EPIC-036E: heartbeat, so an app crash raises an alert.
- The rest of EPIC-041 (docs).
- A suspected `BinanceWebsocketQueueOverflow`.

## Scheduled tasks and records

- Weekly digest: `trig_0159pdYFGSeBxbKVQN8s67k8`, Sundays 08:46 Asia/Ho_Chi_Minh, fires into the coordinator session that created it. When a new coordinator takes over, repoint it with `update_trigger`, or delete it and recreate it from the new session.
- VPS: a Spot mainnet bot `For_VPS` runs on ETHUSDT under the headless host. Alerting goes to Discord. The runbook is `Docs/OPERATIONS/headless_runbook.md`.
