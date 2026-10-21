# EPIC-045G — the four Bots tab actions the host cannot do at runtime yet

**Status:** 🔵 Backlog
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
To decide when the slice starts: one decision record per gap if any is not settled by the owner's rule. Each verb follows the `bot edit` path (a `HostControlAction` word, the closed shape of anything new in the command document, the tab's own command under `BotCommandLock`).

## 3a. Reuse
To decide when the slice starts.

## 4. Changes, per file
To decide when the slice starts.

## 5. Testing
Unit (codec, handlers, verbs), the fake-exchange journey, and the parity guard going green with the exclusions deleted.

## 6. Docs touched
`Docs/OPERATIONS/headless_runbook.md` §6, `Docs/SPEC/SPEC-015_run_the_bots_headless.md`, the bots module docs.
