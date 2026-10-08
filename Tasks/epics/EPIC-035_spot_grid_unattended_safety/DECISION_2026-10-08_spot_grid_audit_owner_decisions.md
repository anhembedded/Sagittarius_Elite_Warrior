# ADR — The Spot Grid audit is acted on in four phases; Phase 1 gates unattended mainnet

**Epic:** [EPIC-035](README.md)
**Date:** 2026-10-08
**Status:** Accepted (D1–D6)
**Decided by:** the owner, 2026-10-08, relayed by the coordinator session; D4 and D6 were decided later the same day

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🔵 Proposed | an option awaiting a decision; not accepted |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |
| ❓ Open | blocks the named phase until answered |

## 1. Context
A static code review of the Spot Grid bot at `master-warrior` `3bbe243` (2026-10-08; published for the owner at https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz) found per-order safety sound (client order ids before submission, lookup of unknown outcomes, adoption by tag after a crash, Stop complete only at zero open tagged orders) and **supervision of a running bot as a whole** weak: stop-loss and take-profit depend on a chart being open, fills during a websocket gap are lost, the user-data stream can end for good, and nothing reaches a user who is away. The audit lists 6 high, 12 medium and 11 low findings in four phases; its §7 asked four questions, answered below.

Phase 1's claims were re-verified against the code on 2026-10-08 by the session that wrote this epic (✅ Established, per task in [`EPIC-035A`](completed/EPIC-035A_the_bot_owns_its_price_subscription.md), [`035B`](completed/EPIC-035B_the_user_data_stream_heals_itself_and_catches_up.md), [`035C`](completed/EPIC-035C_no_unmanaged_orders_and_no_stuck_states.md)). One refinement (H5) and one claim not reproducible here (the python-binance 1.0.37 `ValueError`) are recorded in those tasks.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | Phase 1 (035A, 035B, 035C) is approved and runs under the normal process: feature pull requests, the `ci-local.ps1 -Full` gate, a reviewer session per pull request (`ONBOARDING.md` §7) | Accepted | 🟢 user decision, 2026-10-08 | Three code PRs, one per child; each is a feature PR, so the user merges after a green `-Full` run and a reviewer's read. Phase 1 gates unattended mainnet |
| D2 | Stop-loss stays optional. No default change and no forced warning | Accepted | 🟢 user decision, 2026-10-08 | `EPIC-035L` (H7) carries no "SL is off" Start warning and no SL default; the audit's recommended warning is not built. A bot without SL is still halted by the staleness rule and the range-exit alert, never by a price rule the owner did not set |
| D3 | The alert channel for an absent user is Discord, through a webhook | Accepted | 🟢 user decision, 2026-10-08 | (Delivery moved to [`EPIC-036`](../EPIC-036_alerting_module/README.md), 2026-10-08: `EPIC-036C` builds the Discord adapter; `EPIC-035K` is cancelled.) `EPIC-035K` builds a Discord adapter behind an `INotifier`-style port so another channel is one new adapter. The webhook URL is a secret: keyring only, never a log line, a config file or a traceback |
| D4 | Start with the price outside the range (H7): option **(a)** — the price **below the lower bound is REFUSED** (Start would market-buy the whole capital), the price **above the upper bound is a WARNING only** and Start is allowed. Option (b), WARNING only, was not chosen | Accepted (2026-10-08) | 🟢 user decision, 2026-10-08 (relayed by the coordinator session) | Two new verdicts in `grid_checks.py` (a refusal and a warning), worded for the user; the range-exit alert while running is unaffected. Specified in `EPIC-035L` |
| D5 | Two tasks are added to Phase 3 beside 035K: `EPIC-035W` (the bot's health is visible on screen) and `EPIC-035X` (every bot decision is in an audit trail). The owner requested them on 2026-10-08 and asked that they **not be started yet** | Accepted (2026-10-08) | 🟢 user decision, 2026-10-08 (relayed by the coordinator session) | Two documentation-only task files, no code. 035K's Discord heartbeat reuses 035W's health snapshot and quotes 035X's journal, so both are ordered before or with 035K when started. 035W supersedes the status-bar line of 035N. The storage of the journal (JSON lines or SQLite) is decided inside 035X |
| D6 | **Overrides what `EPIC-035G` shipped in PR #436** ("a running bot goes on trading on memory when its state file cannot be written"). After **3 consecutive failed saves** a running bot goes to **PAUSED** with the reason `STORAGE_FAILURE`. Its resting orders stay on the exchange and nothing new is placed (counter orders are held, as a pause already does). The user's Resume ends it once a save succeeds; while the store still fails, Resume is refused and the bot stays PAUSED. A successful save resets the count. Nothing fails silently: every failed save is logged for the user (WARNING 1/3 and 2/3 with a retry, ERROR from the third), the pause tells the user to check the disk and press Resume, and recovery is logged | Accepted (2026-10-08) | 🟢 user decision, 2026-10-08 (relayed by the coordinator session) | A deliberate behaviour change, not a weakened test: `test_a_running_bot_on_a_failing_disk_goes_on_and_the_next_write_catches_up` is replaced by `test_grid_storage_pause.py`. `GridReason.STORAGE_FAILURE`, `BotRunState.failed_saves` and `GridStorageWatch` (a collaborator of `GridTaskGuard`, so `GridExecutor` gains no public member). The count is read when a worker task ends. The Discord alert on the pause is a follow-up for `EPIC-035K` |

## 3. Alternatives considered
- **D2, a default stop-loss about 5 % below the lower bound** (the audit's alternative). Lost: the owner keeps the choice with the user; a default would change the money-at-risk of every new bot.
- **D3, OS notifications and a tray icon first, then Telegram or email** (the audit's recommendation). Lost to the owner's choice of Discord, which reaches a phone with no extra app code. An OS or tray adapter stays one more adapter on the same port.
- **D6, keep trading on memory** (035G's first answer, a price knowingly paid). Lost to the owner's choice: a bot that cannot save cannot be reconciled from its own file and the screen cannot say so, so it must stop placing. Pausing, not halting, because a halt takes the ladder off the exchange and the disk is the thing that failed; a pause costs nothing the user cannot undo with one Resume.
- **D4 (b), WARNING only.** Lost: it lets the user lay a full-capital opening buy below the range after a one-line warning. Option (a), chosen, costs a refusal the user cannot override while the price is below the range; the range can be edited, so the refusal is never a dead end.

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| — | None open. O1 (D4) was answered on 2026-10-08: option (a) | — | 2026-10-08 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | [035A](completed/EPIC-035A_the_bot_owns_its_price_subscription.md), [035B](completed/EPIC-035B_the_user_data_stream_heals_itself_and_catches_up.md), [035C](completed/EPIC-035C_no_unmanaged_orders_and_no_stuck_states.md) | Partly: 035C delivered (PR #429); 035B delivered in PR #431; 035A delivered in PR #430 | 035C: see its implementation notes; the rest not yet verified |
| D2 | [035L](completed/EPIC-035L_range_exit_and_start_outside_the_range.md) | Held: no stop-loss warning and no default added | `test_no_stop_loss_warning_and_no_default_stop_loss` |
| D3 | [035K](cancelled/EPIC-035K_alerts_reach_a_user_who_is_away.md), superseded by [`EPIC-036`](../EPIC-036_alerting_module/README.md) | Moved to `EPIC-036` (2026-10-08): Discord is `EPIC-036C` | Not yet verified |
| D4 | [035L](completed/EPIC-035L_range_exit_and_start_outside_the_range.md) | Delivered (PR pending); the alert waits for 036B | `tests/unit/modules/bots/domain/grid/test_grid_range_checks.py` (red before, green after) |
| D5 | [035W](incomplete/EPIC-035W_the_bots_health_is_visible_on_screen.md), [035X](incomplete/EPIC-035X_every_bot_decision_is_in_an_audit_trail.md) | Recorded, deliberately not started (owner) | Not yet verified |
| D6 | [035G](completed/EPIC-035G_a_failed_store_write_still_parks.md) (amended) | Delivered (PR pending) | `tests/unit/modules/bots/application/services/test_grid_storage_pause.py` (red before, green after) |
