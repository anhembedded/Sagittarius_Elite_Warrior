# BOT-219 — The Strategies dock is removed from the Bots mode, and arming a strategy stays possible

**Status:** 🔵 Backlog
**Priority:** P2
**Board:** The owner asked to delete the Bots mode's Strategies dock, but it is the only way to arm or disarm a strategy in the app; waiting for the coordinator's choice among the options in §3 (recommended: remove the dock, keep Bots → Arm strategy… and Disarm strategy as dialogs).
**Source:** the delivery coordinator (session_016sGQHsRy729Fp4cY1cTXfu), 2026-10-21, quoting the owner: "… xóa cái strategy luôn đi" ("… and delete the Strategies one"), with the instruction to verify where arming lives first and to stop before deleting if the dock is the only way.
**Risk:** 🔴 — removes SPEC-010's only UI to arm and disarm a strategy
**Complexity:** M — the commands act on the panel's selected venue today
**Epic (optional):** [EPIC-040](../epics/EPIC-040_backtest_workbench/README.md)
**Depends on:** [BOT-218](../completed/BOT-218_one_plan_column_on_the_live_and_backtest_tabs.md)

---

## 1. Context and problem
Verified at `4eade242`: the Trade desk has no Strategy panel (`desk_view.py`: "arming a strategy is the Bots mode's"); `Bots → Arm strategy…` and `Disarm strategy` (`bots_commands.py` `ARM_STRATEGY`, `DISARM_STRATEGY`) act on the selected venue of the Strategies dock (`strategies/strategy_rows.py` `StrategiesPanel`, HLD §11.2 row 126); the only other entry is the `trade-once` CLI, which neither arms nor disarms. Deleting the dock as it is would delete the feature. EPIC-040G D11 ("the Strategies panel keeps working unchanged until G5") is superseded for the Bots screen by the owner's request, to be recorded in the decision file when this is done.

## 2. Acceptance criteria
- [ ] The Bots mode has no Strategies dock, and a saved layout that had it restores without it.
- [ ] A strategy can still be armed and disarmed from the app on each venue (SPEC-010 steps unchanged), and what is armed is still told somewhere the person sees.
- [ ] EPIC-040G D11 is marked superseded for the Bots screen.

## 3. Design
Options: (A) remove the dock, keep both commands: Arm opens its existing dialog with the venue in it; Disarm asks which armed venue in a small chooser (none when one is armed); an armed strategy is told in the Output pane and the Arm dialog. (B) move the table to a tab of the bottom docks. (C) delete arming (loses SPEC-010). Recommended: A, since it honours the request and keeps the feature; its cost is that the armed state is no longer always visible.

## 3a. Reuse
To be filled when the option is chosen.

## 4. Changes, per file
To be filled.

## 5. Testing
To be filled.

## 6. Docs touched
To be filled.
