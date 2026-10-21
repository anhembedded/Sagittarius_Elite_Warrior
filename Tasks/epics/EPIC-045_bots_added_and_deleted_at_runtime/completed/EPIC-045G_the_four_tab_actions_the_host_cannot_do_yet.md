# EPIC-045G — the four Bots tab actions the host cannot do at runtime yet

**Status:** ✅ Done (2026-10-21)
**Source:** the owner's rule of 2026-10-21 ("whatever the UI can do at runtime, the VPS must be able to do"), recorded in `Tasks/COORDINATION.md`; the parity guard of [EPIC-045D](EPIC-045D_the_tab_and_the_host_cannot_drift.md) found the gaps and review round 1 of #697 added the fourth. The coordinator's brief: delete+add is not parity.
**Risk:** 🔴 — arming a strategy on a mainnet venue is real money.
**Complexity:** L
**Epic:** [EPIC-045](../README.md)
**Depends on:** [EPIC-045D](EPIC-045D_the_tab_and_the_host_cannot_drift.md) merged

---

## 1. Context and problem
The guard lists four `OPEN GAP` exclusions: (1) **confirm a HALTED bot's resume** (`ConfirmBotResumeCommand`): only `run --resume-halted` answers it, which acts at host start, so a bot that halts on a running host needs a host restart; (2) **change a DRAFT's venue** (`ChangeBotVenueCommand`): the host has delete + add, a new bot id; (3) **Arm strategy** and (4) **Disarm strategy**: the trading module's armed-strategy controls, with no host verb.

## 2. Acceptance criteria
- [x] A DRAFT's venue is changed on a running host by one verb (for example `bot edit <id> --set venue=<venue>` if the edit path can carry it, otherwise a dedicated verb), through the tab's own `ChangeBotVenueCommand`, under the Start lock, keeping the bot id.
- [x] A HALTED or AWAITING_RECOVERY bot's resume is confirmed on a running host by a verb, through the tab's own Resume and Confirm, with the ladder read by a person first (the verb shows the proposal before it confirms; decide how in the slice's decision).
- [x] Arm and disarm a strategy on a running host through the command directory, reusing the tab's own arm and disarm use cases; an arm on a mainnet venue needs `--confirm-venue`; a position open on the symbol refuses the disarm, in words.
- [x] Each of the four exclusions in the parity guard is deleted by the change that closes it, and the guard then enforces the verb.

## 3. Design
[The decision record](../DECISION_2026-10-21_the_host_does_the_four_tab_actions_left.md): G1 (`bot move`) is decided; G2 and G3 are the owner's (O1, O2), because they are real money. Each verb follows the `bot edit` path (a `HostControlAction` word, the closed shape of anything new in the command document, the tab's own command under `BotCommandLock`).

## 3a. Reuse
To decide when the slice starts.

## 4. Changes, per file
To decide when the slice starts.

## 5. Testing
Unit (codec, handlers, verbs), the fake-exchange journey, and the parity guard going green with the exclusions deleted.

## 6. Docs touched
`Docs/OPERATIONS/headless_runbook.md` §6, `Docs/SPEC/SPEC-015_run_the_bots_headless.md`, the bots module docs.

## Implementation notes (written when done)
**Part 1, the venue change (built):** `bot move <id> --venue <venue>`; `move` action and `to_venue` key; `MoveBotForHostCommandHandler` dispatching the tab's `ChangeBotVenueCommand` under the lock; a same-name-on-the-target-venue refusal the tab does not make; the parity guard's row is now a `HostVerb`. Mutation-checked (the same-venue check, the lock, the venue refusal, the duplicate check on name and on venue). The composed-app journey proves the bot keeps its id and parameters, nothing is placed, and `bot start` is still refused without the typed venue. Not run: the VPS; the `-Full` result on the pull request head.
**Part 2, confirm-resume (built):** owner decision O1, two steps. `bot resume <id>` on a HALTED or AWAITING_RECOVERY bot dispatches the tab's `ResumeBotCommand` (mainnet needs `--confirm-venue`) and replies that a proposal was asked for and nothing is placed; `bot confirm-resume <id>` (`confirm-resume` action word, `ConfirmBotResumeForHostCommand`, `ConfirmResumeForHostCommandHandler`) dispatches the tab's `ConfirmBotResumeCommand`, needs `--confirm-venue` on mainnet too, and refuses a bot with no held proposal in words. No new document key. The parity guard's `ConfirmBotResumeCommand` row is now a `HostVerb`. Mutation-checked: the mainnet venue check on the confirmation, the no-proposal words, the real-money check at the resume for HALTED states, and the proposal reply. A fake-exchange journey proves the resume leaves the bot HALTED with nothing resting and the confirmation lays the ladder.
**Part 3, arm and disarm (built):** owner decision O2. `bot arm-strategy --venue <venue>` and `bot disarm-strategy --venue <venue>` (two action words, one new document key `strategy_venue`, `bot_id` the fixed word `strategy`), handled in the bots application layer by `ArmStrategyForHostCommandHandler` and `DisarmStrategyForHostCommandHandler` over trading's `IVenueStrategyControls`: the very ports the tab's `StrategyArmingCoordinator` asks. The arm takes the venue's **saved arming** (nothing typed), refuses a venue that already has a strategy armed and a venue with no saved arming, and on a mainnet venue needs `--confirm-venue` before it asks the port anything (an armed strategy trades by itself); the disarm asks none, sells and cancels nothing, and a position open on the symbol refuses it in the tab's words. The tab's refusal sentences moved to one table (`strategy_arm_words.py`) the screen and the host both read. The parity guard's Arm and Disarm exclusions are now `HostVerb`s and the guard holds no `Excluded` row. Mutation-checked: the mainnet check, the already-armed check, the saved-arming check, arming the saved arming and not another, the disarm position refusal and the nothing-armed refusal, the codec's disarm-asks-no-venue rule and its subject rule. The composed-app journey arms the saved arming, refuses a second arm, disarms and refuses a second disarm, and places no order. Not run: a mainnet arm on the composed app (the fake exchange holds no mainnet key), the VPS, and the `-Full` result on the pull request head.

## Resume
Done: all four exclusions are gone from the guard. What remains of the epic is [045C](../incomplete/EPIC-045C_bot_apply_beside_a_running_host.md), `bot apply` beside a host.
