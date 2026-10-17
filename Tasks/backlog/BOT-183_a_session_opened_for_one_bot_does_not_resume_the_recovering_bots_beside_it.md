# BOT-183 — Opening a venue's order session for one bot does not put the recovering bots beside it back to trading

**Status:** 🔵 Backlog
**Priority:** P2
**Board:** `EPIC-029J1b` closed the Start path (a Start waits while a bot of the venue is `RECOVERING`); a halted-bot Resume, `run --resume-halted` and the operator's `bot stop` open the same session and still reconcile every `RECOVERING` bot of the venue.
**Source:** the coordinator's brief for `EPIC-029J1b` (2026-10-17): the latent risk `EPIC-042E` recorded, "a halted-bot resume reopens the venue's order session and reconciles every RECOVERING bot of that venue".
**Risk:** 🔴 — a real-money bot the owner did not resume starts laying orders because another bot's command opened the session.
**Complexity:** M — the opener is known in `bots`, the event is published in `trading`; the fix is one more field on the event or one more parameter on `ensure_ready`, and every implementer and fake of the port.
**Epic (optional):** [EPIC-029](../epics/EPIC-029_bots_tab_grid_fast_track/README.md)
**Depends on:** `EPIC-029J1b` (done by the pull request that files this).

---

## 1. Context and problem
`BotEventRouter.on_switch` (`src/modules/bots/application/event_handlers/bot_event_router.py`, at the commit this was filed) answers `TradingSwitchChangedEvent(enabled=True)` by posting `on_switch(True, cause)` to every executor of the venue that is not at rest, and `GridFacts._apply_switch` (`.../kinds/grid/grid_facts.py`) runs `reconcile_recovering()` for a `RECOVERING` one. The event says only that the session opened, not for whom. So any command that opens the session resumes every `RECOVERING` bot of the venue, including bots the owner left for `--resume-recovering` (ADR 038 O2: a host never resumes a bot by itself).

With one active bot per venue (`EPIC-029J1a`) no second bot could be active beside a `RECOVERING` one. `EPIC-029J1b` allows several, and measured it on the fake exchange: after a restart with a Spot bot `RECOVERING`, starting a bot on another symbol opened the session and the first bot returned to `RUNNING` with its ladder laid. `EPIC-029J1b` closed that path for **Start** (`venue_recovering`, item `RUN_VENUE_RECOVERING`). Still open, because they open the session on a venue that can hold a `RECOVERING` bot:
- a Resume of a `HALTED` bot (`BotRunner.resume`, `order_session_refusal`), the desktop's and the host's `--resume-halted`;
- the operator's `bot stop` on a running host (`StopBotForOperatorCommandHandler`, `EPIC-038J`);
- the owner's Resume of one `RECOVERING` bot, which reconciles the others of the venue as well (the owner may want that or not).

On Futures the first opening is refused while a `RECOVERING` bot's position is not yet an owner's (`unexpected_positions`), which protects the common restart; Spot has no such refusal.

## 2. Acceptance criteria
- [ ] The owner decides (one question, with options): may a Resume, `--resume-halted` or an operator stop of bot X resume a `RECOVERING` bot Y of the same venue? Recommended: no; Y waits for its own Resume or `--resume-recovering`.
- [ ] The session opening names who it was for, and only that bot (and any `STOPPING` or owed-cancel bot of the venue) acts on the switch-on event; a `RECOVERING` bot acts only on its own Resume, `--resume-recovering` or an explicit owner enable.
- [ ] A test on the composed app: a `RECOVERING` bot stays `RECOVERING` when another bot's Resume or stop opens the session; then resumes on its own command.

## 3. Design
Not written. Candidate: `ITradingSession.ensure_ready(for_owner=...)` and `TradingSwitchChangedEvent.opened_for`, with `BotEventRouter.on_switch` reconciling `RECOVERING` only for `opened_for` being that bot or `None` (the owner's desktop enable). Touches `trading` contracts, so every implementer and fake of the port changes in the same commit (`architecture-rule.md` §2).

## 3a. Reuse
`order_session_opening` (the one place the bot-side actions open the session), `TradingSwitchChangedEvent`.

## 4. Changes, per file
Written when the task starts.

## 5. Testing
Written when the task starts.

## 6. Docs touched
`Docs/MODULES/bots/06-runtime.md`, `Docs/OPERATIONS/headless_runbook.md` §8 (the paragraph that tells the owner to resume recovering bots first).

## Implementation notes (written when done)
