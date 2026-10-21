# BOT-216 — Toolbar commands show an icon beside their text, which needs the Engine's toolbar style decided

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** Only "Run backtest" has a command icon, and an Engine toolbar shows only the icon when an action has one, so icons on text commands ("Check gaps", "Export plan…") would turn them into unlabelled glyphs. Decide the toolbar style (text beside icon) with the Engine's owner, then give the toolbar commands their Lucide icons (`PRO-009` B6, left out of `EPIC-043E` for this reason).
**Source:** `EPIC-043E`, 2026-10-21. `PRO-009` §2 B6: "commands and states get SVG icons from the existing Lucide set". States got theirs in `043C`/`043E`; commands did not.
**Risk:** 🟡 — a change in the Engine's `workbench_shell`/`action_registry` look affects every mode; an Engine change needs its own confirmation (`ONBOARDING.md` §2)
**Complexity:** M — an Engine decision, then about 20 commands each with an existing icon and a test
**Epic (optional):** [EPIC-043](../epics/EPIC-043_financial_visual_language/README.md)
**Depends on:** the Engine owner's decision on the toolbar style.

---

## 1. Context and problem
`action_registry` calls `action.setIcon(self._icon_loader(descriptor.icon_name))` when a command declares `icon=`, and a mode's toolbar draws an action with an icon as the icon alone (the default tool button style; `workbench_shell` sets `ToolButtonIconOnly` for the mode bar). In `src/` only `backtest_commands.py` passes `icon=` for a command (`"play"` for Run backtest); the other ~20 toolbar commands (`on_toolbar=True`: Trade's Enable live trading, Emergency stop, New order…; Bots' New bot…, Export plan…; Data's Check gaps, Repair gap, Stop, Scan status; Market's zoom and chart commands) are text. Giving them an icon with the toolbar as it is would hide their words, and `ui-presentation-rule.md` §6 requires an icon-only action to carry a tooltip naming its shortcut.

## 2. Acceptance criteria
- [ ] A toolbar command with an icon shows the icon and its text (or the owner decides icon-only with a tooltip naming the shortcut, recorded).
- [ ] Each toolbar command has a Lucide icon from `src/support/ui_kit/assets/icons/` (new icons added to `REQUIRED_UI_ICONS`); no emoji.
- [ ] The workbench conformance suite stays green at all three sizes (a toolbar with text and icons is wider).

## 3. Design (the question, with the options)
1. **Text beside icon for every mode toolbar** (an Engine setting, `setToolButtonStyle` on the mode toolbars). Keeps the words; wider toolbars, which the conformance suite measures.
2. **Icon-only with tooltips** for commands whose icon is the established convention (play, stop), text for the rest: two looks on one toolbar, per command.
3. **Leave commands as text** and keep icons for navigation and states only.
Recommendation: option 1 once the Engine accepts it, because it keeps every command's words (MS `cmd-toolbars`); until then option 3 is what the application does.

## 3a. Reuse
The existing icon set and `IconLoader`; `ActionDescriptor.icon_name`.

## 4. Changes, per file
To be filled when the Engine decision is made.

## 5. Testing
To be filled when the task starts: the conformance suite at the three sizes, and a test per command that its action has an icon and keeps its text.

## 6. Docs touched
`.claude/rules/ui-presentation-rule.md` §4 and §6, `Docs/HLD/11_desktop_workbench.md` (the toolbar).
