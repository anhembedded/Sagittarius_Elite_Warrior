# ADR — The Spot Grid audit is acted on in four phases; Phase 1 gates unattended mainnet

**Epic:** [EPIC-035](README.md)
**Date:** 2026-10-08
**Status:** Accepted (D1–D4)
**Decided by:** the owner, 2026-10-08, relayed by the coordinator session; D4 was decided later the same day

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🔵 Proposed | an option awaiting a decision; not accepted |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |
| ❓ Open | blocks the named phase until answered |

## 1. Context
A static code review of the Spot Grid bot at `master-warrior` `3bbe243` (2026-10-08; published for the owner at https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz) found per-order safety sound (client order ids before submission, lookup of unknown outcomes, adoption by tag after a crash, Stop complete only at zero open tagged orders) and **supervision of a running bot as a whole** weak: stop-loss and take-profit depend on a chart being open, fills during a websocket gap are lost, the user-data stream can end for good, and nothing reaches a user who is away. The audit lists 6 high, 12 medium and 11 low findings in four phases; its §7 asked four questions, answered below.

Phase 1's claims were re-verified against the code on 2026-10-08 by the session that wrote this epic (✅ Established, per task in [`EPIC-035A`](incomplete/EPIC-035A_the_bot_owns_its_price_subscription.md), [`035B`](incomplete/EPIC-035B_the_user_data_stream_heals_itself_and_catches_up.md), [`035C`](completed/EPIC-035C_no_unmanaged_orders_and_no_stuck_states.md)). One refinement (H5) and one claim not reproducible here (the python-binance 1.0.37 `ValueError`) are recorded in those tasks.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | Phase 1 (035A, 035B, 035C) is approved and runs under the normal process: feature pull requests, the `ci-local.ps1 -Full` gate, a reviewer session per pull request (`ONBOARDING.md` §7) | Accepted | 🟢 user decision, 2026-10-08 | Three code PRs, one per child; each is a feature PR, so the user merges after a green `-Full` run and a reviewer's read. Phase 1 gates unattended mainnet |
| D2 | Stop-loss stays optional. No default change and no forced warning | Accepted | 🟢 user decision, 2026-10-08 | `EPIC-035L` (H7) carries no "SL is off" Start warning and no SL default; the audit's recommended warning is not built. A bot without SL is still halted by the staleness rule and the range-exit alert, never by a price rule the owner did not set |
| D3 | The alert channel for an absent user is Discord, through a webhook | Accepted | 🟢 user decision, 2026-10-08 | `EPIC-035K` builds a Discord adapter behind an `INotifier`-style port so another channel is one new adapter. The webhook URL is a secret: keyring only, never a log line, a config file or a traceback |
| D4 | Start with the price outside the range (H7): option **(a)** — the price **below the lower bound is REFUSED** (Start would market-buy the whole capital), the price **above the upper bound is a WARNING only** and Start is allowed. Option (b), WARNING only, was not chosen | Accepted (2026-10-08) | 🟢 user decision, 2026-10-08 (relayed by the coordinator session) | Two new verdicts in `grid_checks.py` (a refusal and a warning), worded for the user; the range-exit alert while running is unaffected. Specified in `EPIC-035L` |

## 3. Alternatives considered
- **D2, a default stop-loss about 5 % below the lower bound** (the audit's alternative). Lost: the owner keeps the choice with the user; a default would change the money-at-risk of every new bot.
- **D3, OS notifications and a tray icon first, then Telegram or email** (the audit's recommendation). Lost to the owner's choice of Discord, which reaches a phone with no extra app code. An OS or tray adapter stays one more adapter on the same port.
- **D4 (b), WARNING only.** Lost: it lets the user lay a full-capital opening buy below the range after a one-line warning. Option (a), chosen, costs a refusal the user cannot override while the price is below the range; the range can be edited, so the refusal is never a dead end.

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| — | None open. O1 (D4) was answered on 2026-10-08: option (a) | — | 2026-10-08 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | [035A](incomplete/EPIC-035A_the_bot_owns_its_price_subscription.md), [035B](incomplete/EPIC-035B_the_user_data_stream_heals_itself_and_catches_up.md), [035C](completed/EPIC-035C_no_unmanaged_orders_and_no_stuck_states.md) | Partly: 035C delivered (PR #429); 035A and 035B pending | 035C: see its implementation notes; the rest not yet verified |
| D2 | [035L](incomplete/EPIC-035L_range_exit_and_start_outside_the_range.md) | Not started | Not yet verified |
| D3 | [035K](incomplete/EPIC-035K_alerts_reach_a_user_who_is_away.md) | Not started | Not yet verified |
| D4 | [035L](incomplete/EPIC-035L_range_exit_and_start_outside_the_range.md) | Not started | Not yet verified |
