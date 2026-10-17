# EPIC-042E — The owner resumes HALTED bots on the headless host with run --resume-halted

**Status:** ✅ Done (2026-10-17; pull request open)
**Source:** the owner, 2026-10-17, through the coordinating session (decision record [D2, D13](../DECISION_2026-10-17_halt_auto_recovery.md))
**Risk:** 🟡 — it lays ladders on real money at a command line; the venue must be named
**Complexity:** M — one flag, one host step, one host command handler
**Epic (optional):** [EPIC-042](../README.md)
**Depends on:** [EPIC-042B](../completed/EPIC-042B_awaiting_recovery_state_and_ledger.md)

---

## 1. Context and problem
`run` has `--resume-recovering` and no way to resume a `HALTED` bot; the `bot` verbs are list, show, apply and export.

## 2. Acceptance criteria
- [x] `--resume-halted` is declared in `cli_commands.json` and read into `RunOptions.resume_halted`; with neither it nor `--resume-recovering` the host does what it does now.
- [x] Done in `042B` (`RESUME_PROPOSES_STATES`): `ResumeBotCommandHandler`, `BotRunner` and `GridExecutor` treat `AWAITING_RECOVERY` as `HALTED`, so the mainnet real-money confirmation and the readiness check apply. This task's host command inherits it and adds the flag's own test.
- [x] A host step resumes every bot in `HALTED` or `AWAITING_RECOVERY` (no other state) through `ResumeBotCommand` then `ConfirmBotResumeCommand`, so the ladder is the GUI's.
- [x] A mainnet venue is resumed only when `--confirm-venue` names it; otherwise the bots are skipped, said so, and stay as they are.
- [x] Refused when no alert channel is configured (the existing "nobody watching" check), with the flag named in the sentence.
- [x] The step's outcome is a line per bot (`[resume-halted]`), and the flag is in the `[run]` line as `--resume-recovering`'s is. (The health snapshot file carries no step outcome for either flag, so there was nothing to match there.)
- [x] A venue whose session will not open leaves its bots untouched, with the reason in the session's words.

## 3. Design
Mirrors `ResumeRecoveringBots` in `host_steps.py` and `StartBotForHostCommandHandler`. The step is the host's; the bot module owns the per-bot command, so `operations` imports only `bots/contracts`.

## 3a. Reuse
Used the screen's `ResumeBotCommand` and `ConfirmBotResumeCommand` (which open the order session through `order_session_refusal_words`), `IBotRunner`, the host-step list and `IMonotonicClock`. `closed_venue_refusal` was named here at the draft and no longer exists (EPIC-039L C4-lite).

## 4. Changes, per file
`operations/cli/run_options.py`, `run_command.py`, `cli_commands.json`, `operations/application/host_steps.py`, `bots/contracts/host_bot_requests.py`, a `resume_halted_for_host` use case, `Docs/OPERATIONS/`, `Docs/MODULES/bots/06-runtime.md`.

## 5. Testing
Unit: option parsing, the mainnet refusal. Integration: the host with a `HALTED` fake bot.

## 6. Docs touched
`Docs/OPERATIONS/` (the flag), `Docs/MODULES/bots/06-runtime.md`, `07-deployment.md`.

## Implementation notes (written when done)
- **Shape.** `ResumeHaltedForHostCommand` (contract) answered by `ResumeHaltedForHostCommandHandler`: for every bot in `RESUME_PROPOSES_STATES` it dispatches the screen's `ResumeBotCommand` (the real-money answer only when `--confirm-venue` names the bot's own venue), then `ConfirmBotResumeCommand` once the bot's worker holds the proposal. `ResumeHaltedBots` is the host step (`[resume-halted]` lines); the flag is in `cli_commands.json` and `RunOptions.resume_halted`.
- **Review fixes (PR review rounds).** One shared 30 s deadline for the whole run (all Resumes first, then polling), so a start-up cannot outlast `TimeoutStartSec`; a proposal not ready in time is withdrawn (`IBotRunner`/`IBotExecutor.withdraw_resume_proposal`, queued behind the Resume) so none stays held to block the automatic recovery; `--resume-halted` runs before `--resume-recovering` so only halts that existed before the start are re-planned; a bot the automatic recovery got to first is reported recovered.
- **Decision recorded (D13, owner may veto).** An unconfirmed mainnet bot is skipped and named in a WARNING instead of refusing the run with exit 2 as `--resume-recovering` does: a pre-boot refusal would have to guess which bots a restart halts, and a skipped resume leaves a bot in a state that already places nothing.
- **Master moved (EPIC-039L C4-lite).** Futures mainnet is open; it is resumed under the same rule as Spot mainnet.
- **Health snapshot.** The task said "in the host's health snapshot as `--resume-recovering`'s is": `--resume-recovering` appears only in the `[run]` line and its own `[resume-recovering]` lines, so `--resume-halted` is in the same two places; the snapshot file has no per-step field.
- **Not verified here:** the owner's Testnet run (phase 3 exit), recorded by the owner.
- **Latent, tied to D20.** The Resume opens the venue's order session, whose switch-on reconciles every RECOVERING bot on that venue, so `--resume-halted` touches no other state only while the fast track keeps a second bot from starting beside a HALTED one (`ONE_RUNNING_BOT_DURING_FAST_TRACK`, probed on the fake exchange by the reviewer). Lifting D20 re-opens whether a halted-bot resume may reconcile a RECOVERING bot the owner left for `--resume-recovering` (O2).
