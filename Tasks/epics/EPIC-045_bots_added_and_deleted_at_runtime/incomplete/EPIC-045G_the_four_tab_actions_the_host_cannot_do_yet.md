# EPIC-045G — the four Bots tab actions the host cannot do at runtime yet

**Status:** 🟡 In progress (G1, the venue change, built; G2 and G3 wait for the owner's answers)
**Source:** the owner's rule of 2026-10-21 ("whatever the UI can do at runtime, the VPS must be able to do"), recorded in `Tasks/COORDINATION.md`; the parity guard of [EPIC-045D](../completed/EPIC-045D_the_tab_and_the_host_cannot_drift.md) found the gaps and review round 1 of #697 added the fourth. The coordinator's brief: delete+add is not parity.
**Risk:** 🔴 — arming a strategy on a mainnet venue is real money.
**Complexity:** L
**Epic:** [EPIC-045](../README.md)
**Depends on:** [EPIC-045D](../completed/EPIC-045D_the_tab_and_the_host_cannot_drift.md) merged

---

## 1. Context and problem
The guard lists four `OPEN GAP` exclusions: (1) **confirm a HALTED bot's resume** (`ConfirmBotResumeCommand`): only `run --resume-halted` answers it, which acts at host start, so a bot that halts on a running host needs a host restart; (2) **change a DRAFT's venue** (`ChangeBotVenueCommand`): the host has delete + add, a new bot id; (3) **Arm strategy** and (4) **Disarm strategy**: the trading module's armed-strategy controls, with no host verb.

## 2. Acceptance criteria
- [ ] A DRAFT's venue is changed on a running host by one verb (for example `bot edit <id> --set venue=<venue>` if the edit path can carry it, otherwise a dedicated verb), through the tab's own `ChangeBotVenueCommand`, under the Start lock, keeping the bot id.
- [ ] A HALTED or AWAITING_RECOVERY bot's resume is confirmed on a running host by a verb, through the tab's own Resume and Confirm, with the ladder read by a person first (the verb shows the proposal before it confirms; decide how in the slice's decision).
- [ ] Arm and disarm a strategy on a running host through the command directory, reusing the tab's own arm and disarm use cases; an arm on a mainnet venue needs `--confirm-venue`; a position open on the symbol refuses the disarm, in words.
- [ ] Each of the four exclusions in the parity guard is deleted by the change that closes it, and the guard then enforces the verb.

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
**Parts 2 and 3 (confirm-resume, arm and disarm):** not started; O1 and O2 in the decision record are the owner's to answer first.

## Resume
Next: the owner's answers to O1 and O2, then one pull request each. This file stays in `incomplete/` until all four exclusions are gone from the guard.
