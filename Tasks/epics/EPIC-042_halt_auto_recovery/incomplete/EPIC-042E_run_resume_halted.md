# EPIC-042E — The owner resumes HALTED bots on the headless host with run --resume-halted

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-17, through the coordinating session (decision record [D2, D13](../DECISION_2026-10-17_halt_auto_recovery.md))
**Risk:** 🟡 — it lays ladders on real money at a command line; the venue must be named
**Complexity:** M — one flag, one host step, one host command handler
**Epic (optional):** [EPIC-042](../README.md)
**Depends on:** [EPIC-042B](EPIC-042B_awaiting_recovery_state_and_ledger.md)

---

## 1. Context and problem
`run` has `--resume-recovering` and no way to resume a `HALTED` bot; the `bot` verbs are list, show, apply and export.

## 2. Acceptance criteria
- [ ] `--resume-halted` is declared in `cli_commands.json` and read into `RunOptions.resume_halted`; with neither it nor `--resume-recovering` the host does what it does now.
- [ ] A host step resumes every bot in `HALTED` or `AWAITING_RECOVERY` (no other state) through `ResumeBotCommand` then `ConfirmBotResumeCommand`, so the ladder is the GUI's.
- [ ] A mainnet venue is resumed only when `--confirm-venue` names it; otherwise the bots are skipped, said so, and stay as they are.
- [ ] Refused when no alert channel is configured (the existing "nobody watching" check), with the flag named in the sentence.
- [ ] The step's outcome is a line per bot (`[resume-halted]`) and in the host's health snapshot as `--resume-recovering`'s is.
- [ ] A venue whose session will not open leaves its bots untouched, with the reason in the session's words.

## 3. Design
Mirrors `ResumeRecoveringBots` in `host_steps.py` and `StartBotForHostCommandHandler`. The step is the host's; the bot module owns the per-bot command, so `operations` imports only `bots/contracts`.

## 3a. Reuse
Used `order_session_refusal_words`, `closed_venue_refusal`, `BotLookup`, the host-step list, `emit_report`.

## 4. Changes, per file
`operations/cli/run_options.py`, `run_command.py`, `cli_commands.json`, `operations/application/host_steps.py`, `bots/contracts/host_bot_requests.py`, a `resume_halted_for_host` use case, `Docs/OPERATIONS/`, `Docs/MODULES/bots/06-runtime.md`.

## 5. Testing
Unit: option parsing, the mainnet refusal. Integration: the host with a `HALTED` fake bot.

## 6. Docs touched
`Docs/OPERATIONS/` (the flag), `Docs/MODULES/bots/06-runtime.md`, `07-deployment.md`.
