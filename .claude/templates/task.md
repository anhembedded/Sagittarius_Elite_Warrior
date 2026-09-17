---
description: The format of a standalone task under Tasks/backlog/ or an epic child under its incomplete/ directory (ONBOARDING §3). Copy it, fill every brace, delete this front matter and instructional comments.
---

# {task id} — {the outcome, not the activity}

<!-- Use BOT-nnn for a standalone task or EPIC-nnnA for an epic child. Choose one value for status, risk and complexity. Remove optional fields that do not apply. -->
<!-- Execute through .claude/skills/execute-task/SKILL.md; completion follows .claude/rules/task-execution-rule.md and chat reports follow .claude/rules/report-task-rule.md. -->
**Status:** {🔵 Backlog / 🟡 In progress / ✅ Done (YYYY-MM-DD) / ❌ Cancelled (YYYY-MM-DD; reason)}
**Source:** {who asked, when — the user's words quoted once, verbatim, then translated}
**Risk:** {🟢 / 🟡 / 🔴} — {what could break, one line}
**Complexity:** {S / M / L} — {why, one line}
**Epic (optional):** {link to the parent epic README}
**SPEC (optional):** {link to the use case this task implements or changes}
**Depends on:** {task links and what must be ready, or None}

---

## 1. Context and problem
{The real situation with evidence: `file:line`, a measured number, the symptom. Why now.}

## 2. Acceptance criteria
- [ ] {An observable outcome, including the conditions under which it must hold.}
- [ ] {A relevant failure or boundary outcome; omit if not applicable.}

## 3. Design
{The choice made and the reason for each non-obvious one; the named pattern or vetted project it applies (ONBOARDING §7: apply before you invent). A restructuring shows as-is and to-be.}

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| {path} | {what, and why} |

## 5. Testing
{Map each acceptance criterion to a test or a manual check with its expected result. Name the tier (`ci-rule.md` §6); for documentation-only work, name the required document guards. Record checks not yet run explicitly.}

## Implementation notes (written when done)
{The real bugs met, decisions taken, verification commands and results tied to the checked revision/snapshot, and the gate's `LOG_FILE:` path when applicable. Link evidence for each acceptance criterion and state the actual delivery state. Follow ONBOARDING §6 for standalone tasks and §12.3 for epic children.}

## Resume (optional; while unfinished)
{The last verified result, unchecked criteria, any blocker and what releases it, and the next executable action. Record partial verification here without claiming Done; update or remove this section once resolved.}
