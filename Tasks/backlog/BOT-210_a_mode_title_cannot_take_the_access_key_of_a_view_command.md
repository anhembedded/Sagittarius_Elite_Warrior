# BOT-210 — Adding a mode cannot make the workbench refuse a View command's access key

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** A mode's View item takes the next free letter in mode order, so adding a mode (`Alerts`, `EPIC-036D2`) pushed `Backtest engine` onto the key of a Market command and the workbench suite refused it on every dev-mode case; the fix moved that one command's key. Decide how the assignment learns the commands' keys so the next mode cannot clash.
**Source:** the delivery coordinator, 2026-10-20: "file the mode access-key collision as a backlog BOT task (one file, the root-fix design question)", after `EPIC-036D2` hit it.
**Risk:** 🟢 — menu text only; the suite already refuses a clash, so a wrong choice fails loudly
**Complexity:** S — one function and its inputs, once the choice is made
**Depends on:** None.

---

## 1. Context and problem
`MainWindow._add_modes` (`src/presentation/ui/main_window.py`, `assign_access_keys(titles, _VIEW_MENU_KEYS)`) gives each mode title the first letter no earlier title and no key in `_VIEW_MENU_KEYS` (`o`, `u`) uses. The View commands of the modes (Market's `S&pot market`, `Futures mar&ket`, `Remove from Watc&hlist`, and so on) are declared with fixed keys elsewhere, and the engine's `ActionRegistry` refuses two labels under one menu that share a key. Nothing connects the two, so a new mode title can shift a later title onto a command's key.

Observed at `bd5eefa` plus `EPIC-036D2` (PR #656): with `Alerts` before `Backtest engine`, Backtest fell from `a` to `c` and met `Remove from Wat&chlist`; every `test_workbench_conformance[True-*]` errored. `EPIC-036D2` moved that command's key to `&from` (a local fix, chosen by trying letters).

## 2. Acceptance criteria
- [ ] Adding a mode to the mode bar cannot produce an access-key clash with a View command, for any mode order, by construction (a test that adds a mode with each letter's title, or a property over the real commands).
- [ ] No existing command key changes except where the chosen design needs it, and the HLD §11.2.3 table says which keys the modes get.

## 3. Design (the question, with the options)
1. **Pass the commands' View keys to `assign_access_keys` as taken.** Tried in `EPIC-036D2`: the View commands of all modes together use so many letters that `Bots` found none and the engine requires exactly one `&`. Needs fewer command keys (only the commands of the always-visible scope) or longer titles.
2. **Scope the check, not the keys.** Mode items and a mode's commands meet only while that mode shows, so the rule is "a mode title may not share a key with the commands of the showing mode", enforced where the registry decides `scopes_meet` (an Engine change, needs its own confirmation per `ONBOARDING.md` §2).
3. **Give each mode a declared key** in its `NavMetadata` and have the window refuse a duplicate: stable keys (no shifting when a mode is added), one more field.
Recommendation: option 3. It removes the order dependence that caused the clash, needs no Engine change, and the HLD already lists planned keys per mode.

## 4. Changes, per file
To be filled when the option is chosen.

## 5. Testing
A guard that builds the real registry with a probe mode and fails on any clash; mutation: give the probe the key of a View command.

## 6. Docs touched
`Docs/HLD/11_desktop_workbench.md` §11.2.3.
