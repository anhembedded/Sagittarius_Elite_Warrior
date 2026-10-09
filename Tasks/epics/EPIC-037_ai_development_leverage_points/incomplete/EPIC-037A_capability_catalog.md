# EPIC-037A — A capability catalog the AI receives when it touches UI or application code

**Status:** 🔵 Planned — not started
**Source:** the owner's systems-thinking review, 2026-10-09 (see the epic README for the quote)
**Risk:** 🟢 — documentation and one generator script; a stale catalog is the main risk
**Complexity:** S — one rule file, one script, one guard
**Epic:** [EPIC-037](../README.md)
**Depends on:** None

---

## 1. Context and problem
Class A ("did not reuse; diverging siblings") is 18 of 192 bug reports, and it grew from 4 to 13+ between the first 103 reports and the next 89 (analysis §2). BUG-155 is the owner's example: the New bot dialog used a free-text symbol field although `src/support/ui_kit/symbol_picker/` (`SymbolPickerOverlay`, `ISymbolPickerSource`) existed; BUG-165 hand-built twelve empty-state labels although `EmptyStateStack` existed. Nothing tells a session what shared mechanisms exist at the moment it decides; the HLD exists but is not delivered then. Verify the cited paths when the task starts.

## 2. Acceptance criteria
- [ ] `.claude/rules/capabilities.md` exists with `paths:` front matter covering `src/modules/**/ui/**` and `src/modules/**/application/**`, so it loads only when a session touches those files; it lists each shared mechanism as *need → use → where → one current user*.
- [ ] Most rows are generated: `scripts/render_capability_index.py` reads a `Capability:` line from module docstrings under `src/support/**` and `src/core/**` and renders the table; a hand-written section may add rows the generator cannot see.
- [ ] A guard fails when a package under `src/support/` has no catalog row, or when a catalog path does not exist.
- [ ] `.claude/templates/task.md` gains a required **Reuse** section ("checked X, Y; used Y because…"), and the pr-review rubric checks it.
- [ ] The always-loaded line count (`measure_process.py`) does not rise.

## 3. Design
Leverage point 6 (information flow), delivered just in time (Anthropic, context engineering, 2025) instead of preloaded. Reuse the existing path-scoped rule loading and the reference checker (`scripts/check_skill_prompt_references.py`) rather than inventing a loader. Generating rows from docstrings keeps the catalog next to the code it describes.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `.claude/rules/capabilities.md` | new, path-scoped catalog |
| `scripts/render_capability_index.py` | new generator |
| `src/support/**`, `src/core/**` module docstrings | add `Capability:` lines |
| `tests/unit/architecture/test_every_support_package_is_in_the_catalog.py` | new completeness guard |
| `.claude/templates/task.md`, `.claude/skills/pr-review/references/rubric.md` | Reuse section and its check |
| `CLAUDE.md` navigation table, `.claude/README.md` | rows for the new rule (`test_rule_navigation_is_complete.py`) |

## 5. Testing
Guard: remove one catalog row and see it red, restore it green. Reference checker green. A manual check: open a UI file in a fresh session and confirm the rule is listed as loaded.

## Implementation notes (written when done)
Not started.
