# Coordination — live state

**Reader:** the coordinator session (`.claude/skills/coordinate/SKILL.md`), which reads this first and updates it after every merge, hand-off or owner decision. **Last updated:** 2026-10-20.

**Coordinator session:** `session_01PZn6EWxn6gytSGKwbuRJGg`. Authors send "ready to merge" here; a new coordinator replaces this line first.

This file holds state, not rules. Rules live in `.claude/`; decisions live in their records. A line here that a record contradicts is wrong: fix the line.

## Owner's standing decisions

| Decision | Where it binds |
| :--- | :--- |
| The coordinator may merge code PRs itself once it has verified the head (gates read, reviewer PASS where one is required, scope matches). Owner's words: *"bạn theo dõi và tự merge hết đi, cho phép"* | `coordinate` skill step 5 |
| Every session, author and reviewer, runs on the one model the owner names (2026-10-25: the owner no longer has the stronger model); the author and the reviewer stay in separate sessions, and a reviewer is created with the repository checked out at the PR branch. When more than one model is available again, the reviewer goes back to a different model from the author's | `coordinate` skill step 3 |
| At most two delivery streams in flight; a weekly digest; design decisions are taught and written to `Docs/LEARNING/` | `report-rule.md` §3 |
| Speak Vietnamese to the owner; repository text in English | `ONBOARDING.md` §10 |
| The model named Fable is never used: not for a session, a created session or a subagent; "strongest model" means the strongest other model (2026-10-17) | `ONBOARDING.md` §7, "Excluded model" |
| EPIC-039L O1: the Emergency Stop cancels regular orders, then closes, then confirms the position is flat, then cancels conditional orders. O2: the Futures mainnet lock is removed with no new mechanism ("tui tự quản rủi ro"). O3 b: take profit stays in-app until after the soak | `Tasks/epics/EPIC-039_futures_venue_profile/DECISION_2026-10-16_futures_protective_stop_minimum.md` §6 |
| EPIC-042: a transient halt waits in `AWAITING_RECOVERY`. Recovery waits for 120 s of continuously clear signal, at most 3 times per 24 h. The policy is layered (common, kind, venue). A restart ends the wait in `HALTED`. A stalled wait raises an alert and keeps waiting | `Tasks/epics/EPIC-042_halt_auto_recovery/DECISION_2026-10-17_halt_auto_recovery.md` |
| EPIC-038 O12 (delegated to the coordinator, 2026-10-20: *"bạn tự quyết định đi"*): the headless host's default stop leaves a Futures bot only while a stop on the exchange covers its position and closes every other one before exit; Spot unchanged; within `--stop-timeout` | `Tasks/epics/EPIC-038_headless_operation/DECISION_2026-10-20_a_futures_bot_at_host_stop.md` |
| 2026-10-21, delegated to the coordinator (owner's words: *"ok, tự quyết đi ní"*, answering the BUG-247 option C hard-line question and the open decisions of that day). `BOT-226`: the weight gate closes to routine requests at 70 % and to every request at 90 % (`HARD_WEIGHT_RATIO`). `BUG-254`: a refusal by the owner's own pacing caps (spacing, rate) is never terminal: retry on another turn, then a `RATE_LIMITED` pause; the one exception is a pause during the opening's later slices, which keeps the close at market, because a resume does not finish an opening. `EPIC-045` O1: `bot delete` keeps a bot whose record holds a base worth 10 quote units or more, a live order or a standing stop; O2: `bot add` lands DRAFT on every venue; D5: `bot apply` beside a running host sits beside `bot add`; slice F: `run --start-planned` skips an unconfirmed real-money bot with a WARNING and an alert and runs the rest | `BOT-226`'s task; `BUG-254`'s decision record in EPIC-029; EPIC-045's decision record |
| 2026-10-21 (owner's words: *"tạo cơ chế add bot, xóa bot runtime đi ... cái gì trên UI runtime dc thì VPS phải dc chứ"*): every Bots tab action that changes a bot has a verb on the running headless host; this reverses the 2026-10-17 choice that dropped `bot delete` from EPIC-038K | EPIC-045's decision record |

## Streams in flight

| Stream | Next step | Author session | Reviewer session | PR | Blocked on |
| :--- | :--- | :--- | :--- | :--- | :--- |
| EPIC-042 halt auto-recovery | 042C merged ([#552](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/552)). Next: 042D, 042E, 042G per the epic README's Resume; 042F waits for the owner | `session_01YAKL8J6qPJTqRGHSezUTUe` | spawned per PR by the author | not yet open | nothing |
| EPIC-039L C4-lite | C3 merged ([#550](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/550)). Futures mainnet lock removed (O2); reviewer PASS round 3 at 1956eca; author merging master into the PR | `session_016ToGGUVsE8ESa454e3eb1T` | `session_012XC79LLm2DLs5XrUNhAkyQ` | [#551](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/551) | author's "ready" at the post-merge head |

Deferred: EPIC-039L D10 and D13 (a halt that leaves the position, stop custody).

## Owner still owes

- Sync the Windows clock. It was 127 s ahead on 2026-10-17. Then Stop and Start the Futures Testnet bot again after pulling BUG-223.
- Check Binance Testnet for leftover `SEW-djwx0w` orders.

## Backlog worth remembering

- BOT-182: the desktop app shows a notice when the clock skew exceeds 1 s.
- EPIC-029J: two copies of the app on one account and symbol.
- EPIC-036E: heartbeat, so an app crash raises an alert.
- The rest of EPIC-041 (docs).
- A suspected `BinanceWebsocketQueueOverflow`.
- **EPIC-047 (VPS Bots tab) resumed by the owner (2026-10-26):** 047A and 047B in parallel first. **EPIC-048 (the UI's doors)** goes on only as far as 047 needs it (048B's second pull request, when 047E starts); 048C and 048D stay paused. See each epic README's **Resume** section.

## Scheduled tasks and records

- Weekly digest: `trig_0159pdYFGSeBxbKVQN8s67k8`, Sundays 08:46 Asia/Ho_Chi_Minh, fires into the coordinator session that created it. When a new coordinator takes over, repoint it with `update_trigger`, or delete it and recreate it from the new session.
- VPS: a Spot mainnet bot `For_VPS` runs on ETHUSDT under the headless host. Alerting goes to Discord. The runbook is `Docs/OPERATIONS/headless_runbook.md`.
