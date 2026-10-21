# BOT-210 — Adding a mode cannot make the workbench refuse a View command's access key

**Status:** ✅ Done (2026-10-21)
**Board:** A mode declares its View access key in its `NavMetadata` (`access_key`), so adding a mode moves no other mode's key; the window refuses a letter not in the title, one two modes share, or one a View item holds, and a test holds every real mode and every real View command to it (option 3, as recommended). No existing key changed.
**Source:** the delivery coordinator, 2026-10-20: "file the mode access-key collision as a backlog BOT task (one file, the root-fix design question)", after `EPIC-036D2` hit it.
**Risk:** 🟢 — menu text only; the suite already refuses a clash, so a wrong choice fails loudly
**Complexity:** S — one function and its inputs, once the choice is made
**Depends on:** None.
**Decided by:** the delivery coordinator for the owner, 2026-10-21: "Take the recommendation unless the code shows it is wrong, and record the choice". The code does not show it wrong (§3).

---

## 1. Context and problem
`MainWindow._add_modes` (`src/presentation/ui/main_window.py`, `assign_access_keys(titles, _VIEW_MENU_KEYS)`) gives each mode title the first letter no earlier title and no key in `_VIEW_MENU_KEYS` (`o`, `u`) uses. The View commands of the modes (Market's `S&pot market`, `Futures mar&ket`, `Remove from Watc&hlist`, and so on) are declared with fixed keys elsewhere, and the engine's `ActionRegistry` refuses two labels under one menu that share a key. Nothing connects the two, so a new mode title can shift a later title onto a command's key.

Observed at `bd5eefa` plus `EPIC-036D2` (PR #656): with `Alerts` before `Backtest engine`, Backtest fell from `a` to `c` and met `Remove from Wat&chlist`; every `test_workbench_conformance[True-*]` errored. `EPIC-036D2` moved that command's key to `&from` (a local fix, chosen by trying letters).

## 2. Acceptance criteria
- [x] Adding a mode to the mode bar cannot produce an access-key clash with a View command, for any mode order, by construction: keys are declared and do not depend on order (`test_adding_a_mode_moves_no_other_modes_key`), and a property over the real modes and the real View commands names any mode key a command also holds (`test_the_real_modes_keys_are_none_of_a_view_commands`; mutated: Alerts on `l`, Backtest on `k`).
- [x] No existing key changes (`test_the_real_modes_keep_the_keys_they_had`), and HLD §11.2.3 names the keys the modes get.

## 3. Design
**Chosen: option 3**, a declared key per mode, as recommended. Checked against the code before taking it: `MainWindow._add_modes` (`src/presentation/ui/main_window.py`) did hand each title the first letter no earlier title used, in mode order, so the clash was order-dependent as §1 says; option 1 (command keys as taken) would need the View commands of every mode to leave letters free for modes that do not exist yet; option 2 needs the Engine's registry (`ONBOARDING.md` §2: its own confirmation). Option 3 needs neither.

`NavMetadata.access_key` (one letter of the title; empty means "the window picks", for a test's fake screen) is read by `mode_labels` (`src/presentation/ui/mode_access_keys.py`), which the window calls. A declaration it cannot honour is a `ModeAccessKeyError` at boot, naming the mode: a letter not in the title, one two modes declare, one the View menu's own items hold (`T&oolbars`, `Stat&us bar`). The keys declared are the ones the window assigned: `m` Market, `t` Trade, `b` Bots, `d` Data, `a` Alerts, `e` Developer, `c` Backtest engine.

The declaration does not prevent a View command taking a mode's letter; it moves the check to one place that sees both, a test over the real contributions, which fails naming the mode and the command, as the suite already did at boot.

## 3a. Reuse
`assign_access_keys` (the Engine's): still used, for a mode that declares none. `real_contributions` (tests): used for the property.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/core/contracts/nav_metadata.py` | `access_key` |
| `src/presentation/ui/mode_access_keys.py` | new: `mode_labels`, `ModeAccessKeyError` |
| `src/presentation/ui/main_window.py` | `_add_modes` uses it |
| the seven screens' `_NAV` | declare their letter |
| `tests/unit/presentation/ui/test_mode_access_keys.py` | new |
| `test_chart_display_commands.py`, `test_market_choice.py` | read the keys the window gives (`mode_labels`), not a copy of the old rule |

## 5. Testing
`tests/unit/presentation/ui/test_mode_access_keys.py` (eleven cases); the two existing guards that simulated the window now call the same function; the conformance suite (`access_keys_unique`) boots the real window.

## 6. Docs touched
`Docs/HLD/11_desktop_workbench.md` §11.2.3 (the View row).

## Implementation notes
Mutation (each turned the new tests red and was restored): Alerts on `l` (a Live chart tab key), Backtest engine on `k` (Mar&ket, Bac&ktest tab), Trade undeclared, the window ignoring a declared key.
